import json
import logging
import os
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime

from src.requirement_analyzer import generate_requirement_schema
from src.dafny_writer import generate_dafny
from src.dafny_verifier import verify_dafny
from src.schema import RequirementSchema
from .judge_schema import judge_schema as judge_schema_fn
from .judge_dafny import judge_dafny as judge_dafny_fn

logger = logging.getLogger(__name__)

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
GROUND_TRUTH_PATH = os.path.join(EVAL_DIR, "ground_truth.json")
RESULTS_PATH = os.path.join(EVAL_DIR, "results.json")
REPORT_PATH = os.path.join(EVAL_DIR, "report.md")


@dataclass
class EvalResult:
    id: str
    nl_requirement: str
    predicted_schema: Optional[dict] = None
    reference_schema: Optional[dict] = None
    predicted_dafny: Optional[str] = None
    reference_dafny: Optional[str] = None
    schema_judge_result: Optional[dict] = None
    dafny_judge_result: Optional[dict] = None
    dafny_verification: Optional[dict] = None
    error: Optional[str] = None


def _verification_to_dict(result) -> dict:
    return {
        "is_valid": result.is_valid,
        "errors": result.errors,
        "verification_passed": result.verification_passed,
        "dafny_output": result.dafny_output,
    }


def load_ground_truth() -> list[dict]:
    with open(GROUND_TRUTH_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["requirements"]


def run_eval(
    limit: Optional[int] = None,
    model: str = "llama3",
    host: Optional[str] = None,
    skip_judge: bool = False,
) -> list[EvalResult]:
    requirements = load_ground_truth()
    if limit is not None:
        requirements = requirements[:limit]

    results: list[EvalResult] = []

    for req in requirements:
        req_id = req["id"]
        nl = req["nl_requirement"]
        gt_schema = req["schema"]

        logger.info("Evaluating %s: %s", req_id, nl[:60])

        result = EvalResult(
            id=req_id,
            nl_requirement=nl,
            reference_schema=gt_schema,
        )

        try:
            # Step 1: Run the pipeline's Layer 1
            logger.info("  [Layer 1] Generating schema from NL...")
            pred_schema_obj: RequirementSchema = generate_requirement_schema(
                nl, model=model, host=host
            )
            pred_schema = pred_schema_obj.model_dump()
            result.predicted_schema = pred_schema

            if skip_judge:
                logger.info("  [Judge] Skipping schema judge (skip_judge=True)")
            else:
                logger.info("  [Judge] Evaluating schema...")
                try:
                    schema_judge = judge_schema_fn(
                        nl_requirement=nl,
                        ground_truth_schema=gt_schema,
                        predicted_schema=pred_schema,
                        model=model,
                        host=host,
                    )
                    result.schema_judge_result = schema_judge
                    logger.info(
                        "  [Judge] Schema score: %.2f",
                        schema_judge.get("score", 0.0),
                    )
                except Exception as exc:
                    logger.error("  [Judge] Schema judge failed: %s", exc)
                    result.schema_judge_result = {"error": str(exc)}

            # Step 2: Run the pipeline's Layer 2
            logger.info("  [Layer 2] Generating Dafny from predicted schema...")
            pred_dafny = generate_dafny(pred_schema_obj, model=model, host=host)
            result.predicted_dafny = pred_dafny

            # Step 3: Generate reference Dafny from ground-truth schema
            logger.info("  [Reference] Generating reference Dafny...")
            gt_schema_obj = RequirementSchema.model_validate(gt_schema)
            ref_dafny = generate_dafny(gt_schema_obj, model=model, host=host)
            result.reference_dafny = ref_dafny

            if skip_judge:
                logger.info("  [Judge] Skipping Dafny judge (skip_judge=True)")
            else:
                logger.info("  [Judge] Evaluating Dafny...")
                try:
                    dafny_judge = judge_dafny_fn(
                        nl_requirement=nl,
                        schema=gt_schema,
                        reference_dafny=ref_dafny,
                        predicted_dafny=pred_dafny,
                        model=model,
                        host=host,
                    )
                    result.dafny_judge_result = dafny_judge
                    logger.info(
                        "  [Judge] Dafny correctness: %s, semantic score: %.2f",
                        dafny_judge.get("is_correct", False),
                        dafny_judge.get("semantic_equivalence_score", 0.0),
                    )
                except Exception as exc:
                    logger.error("  [Judge] Dafny judge failed: %s", exc)
                    result.dafny_judge_result = {"error": str(exc)}

            # Step 4: Verify predicted Dafny
            logger.info("  [Verify] Verifying predicted Dafny...")
            verification = verify_dafny(pred_dafny)
            result.dafny_verification = _verification_to_dict(verification)
            logger.info(
                "  [Verify] Valid: %s, Passed: %s",
                verification.is_valid,
                verification.verification_passed,
            )

        except Exception as exc:
            logger.error("  [Error] Pipeline failed: %s", exc, exc_info=True)
            result.error = str(exc)

        results.append(result)
        save_results(results)

    return results


def save_results(results: list[EvalResult]) -> None:
    serializable = [asdict(r) for r in results]
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)


def compute_summary(results: list[EvalResult]) -> dict:
    total = len(results)
    schema_scores = []
    schema_match_count = 0
    dafny_correct_count = 0
    dafny_semantic_scores = []
    dafny_verified_count = 0
    dafny_valid_count = 0
    errors = 0

    for r in results:
        if r.error:
            errors += 1
            continue

        if r.schema_judge_result and "score" in r.schema_judge_result:
            score = r.schema_judge_result["score"]
            schema_scores.append(score)
            if r.schema_judge_result.get("function_name_match") and score >= 0.8:
                schema_match_count += 1

        if r.dafny_judge_result and "is_correct" in r.dafny_judge_result:
            if r.dafny_judge_result["is_correct"]:
                dafny_correct_count += 1
            semantic = r.dafny_judge_result.get("semantic_equivalence_score", 0.0)
            dafny_semantic_scores.append(semantic)

        if r.dafny_verification:
            if r.dafny_verification["verification_passed"]:
                dafny_verified_count += 1
            if r.dafny_verification["is_valid"]:
                dafny_valid_count += 1

    return {
        "total": total,
        "errors": errors,
        "schema": {
            "avg_score": sum(schema_scores) / len(schema_scores) if schema_scores else 0.0,
            "pass_count": schema_match_count,
            "pass_rate": schema_match_count / total if total else 0.0,
        },
        "dafny": {
            "correct_count": dafny_correct_count,
            "correct_rate": dafny_correct_count / total if total else 0.0,
            "avg_semantic_score": (
                sum(dafny_semantic_scores) / len(dafny_semantic_scores)
                if dafny_semantic_scores
                else 0.0
            ),
            "verified_count": dafny_verified_count,
            "valid_count": dafny_valid_count,
        },
    }


def generate_report(results: list[EvalResult], summary: dict) -> str:
    now = datetime.now().isoformat()
    lines = [
        "# Evaluation Report",
        "",
        "Generated: " + now,
        "",
        "## Summary",
        "",
        "- **Total requirements**: " + str(summary["total"]),
        "- **Pipeline errors**: " + str(summary["errors"]),
        "",
        "### Schema Generation",
        "",
        "- **Average score**: {:.2f}".format(summary["schema"]["avg_score"]),
        "- **Pass count**: {} / {}".format(
            summary["schema"]["pass_count"], summary["total"]
        ),
        "- **Pass rate**: {:.1%}".format(summary["schema"]["pass_rate"]),
        "",
        "### Dafny Generation",
        "",
        "- **Correct (judge)**: {} / {} ({:.1%})".format(
            summary["dafny"]["correct_count"],
            summary["total"],
            summary["dafny"]["correct_rate"],
        ),
        "- **Average semantic equivalence**: {:.2f}".format(
            summary["dafny"]["avg_semantic_score"]
        ),
        "- **Dafny verified**: {} / {}".format(
            summary["dafny"]["verified_count"], summary["total"]
        ),
        "- **Dafny valid (syntax)**: {} / {}".format(
            summary["dafny"]["valid_count"], summary["total"]
        ),
        "",
        "## Detailed Results",
        "",
    ]

    for r in results:
        lines.append("### " + r.id)
        lines.append("")
        lines.append("**Requirement**: " + r.nl_requirement)
        lines.append("")

        if r.error:
            lines.append("**Error**: " + r.error)
            lines.append("")
            continue

        if r.schema_judge_result:
            sj = r.schema_judge_result
            lines.append("**Schema judge score**: " + str(sj.get("score", "N/A")))
            lines.append("")
            if sj.get("differences"):
                lines.append("**Differences**:")
                for d in sj["differences"]:
                    lines.append("- " + d)
                lines.append("")
            if sj.get("reasoning"):
                lines.append("**Reasoning**: " + sj["reasoning"])
                lines.append("")

        if r.dafny_judge_result:
            dj = r.dafny_judge_result
            lines.append("**Dafny is correct**: " + str(dj.get("is_correct", "N/A")))
            lines.append("**Semantic equivalence**: " + str(dj.get("semantic_equivalence_score", "N/A")))
            lines.append("**Matches spec**: " + str(dj.get("matches_specification", "N/A")))
            lines.append("**Would verify**: " + str(dj.get("would_verify", "N/A")))
            lines.append("")
            if dj.get("differences"):
                lines.append("**Differences**:")
                for d in dj["differences"]:
                    lines.append("- " + d)
                lines.append("")
            if dj.get("missing_elements"):
                lines.append("**Missing elements**:")
                for m in dj["missing_elements"]:
                    lines.append("- " + m)
                lines.append("")
            if dj.get("extra_elements"):
                lines.append("**Extra elements**:")
                for e in dj["extra_elements"]:
                    lines.append("- " + e)
                lines.append("")
            if dj.get("reasoning"):
                lines.append("**Reasoning**: " + dj["reasoning"])
                lines.append("")

        if r.dafny_verification:
            dv = r.dafny_verification
            lines.append("**Dafny valid**: " + str(dv["is_valid"]))
            lines.append("**Verification passed**: " + str(dv["verification_passed"]))
            if dv["errors"]:
                lines.append("**Verification errors**:")
                for err in dv["errors"]:
                    lines.append("- " + err)
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def main(
    limit: Optional[int] = None,
    model: str = "llama3",
    host: Optional[str] = None,
    skip_judge: bool = False,
) -> None:
    logging.basicConfig(level=logging.INFO)

    logger.info("Loading ground truth from %s", GROUND_TRUTH_PATH)
    requirements = load_ground_truth()
    logger.info("Loaded %d requirements", len(requirements))

    results = run_eval(
        limit=limit,
        model=model,
        host=host,
        skip_judge=skip_judge,
    )

    summary = compute_summary(results)
    report = generate_report(results, summary)

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)

    logger.info("Results saved to %s", RESULTS_PATH)
    logger.info("Report saved to %s", REPORT_PATH)
    logger.info("Summary: %s", summary)


if __name__ == "__main__":
    main(limit=3)
