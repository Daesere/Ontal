import logging
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Optional


logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    dafny_output: Optional[str] = None
    verification_passed: bool = False


def _find_dafny() -> Optional[str]:
    """Return the path to the Dafny CLI if available."""
    return shutil.which("dafny")


def _basic_syntax_check(code: str) -> VerificationResult:
    """
    Perform lightweight syntactic checks on Dafny code without the compiler.
    This catches common LLM generation mistakes like missing modules or typos.
    """
    errors: list[str] = []

    stripped = code.strip()
    if not stripped:
        errors.append("Dafny code is empty.")
        return VerificationResult(is_valid=False, errors=errors)

    if "module" not in stripped:
        errors.append("No 'module' declaration found.")

    if "method" not in stripped and "function" not in stripped:
        errors.append("No 'method' or 'function' declaration found.")

    # Check for balanced braces (very rough heuristic)
    open_braces = stripped.count("{")
    close_braces = stripped.count("}")
    if open_braces != close_braces:
        errors.append(
            f"Unbalanced braces: {open_braces} opening, {close_braces} closing."
        )

    # Check for markdown fence leakage
    if "```" in stripped:
        errors.append("Code appears to contain markdown fences.")

    return VerificationResult(is_valid=len(errors) == 0, errors=errors)


def verify_dafny(code: str, dafny_path: Optional[str] = None) -> VerificationResult:
    """
    Verify Dafny code using the Dafny CLI if available, otherwise fall back to
    a lightweight syntax check.

    Args:
        code: Raw Dafny source code.
        dafny_path: Optional explicit path to the Dafny executable.

    Returns:
        VerificationResult with validity status, errors, and raw CLI output if run.
    """
    basic = _basic_syntax_check(code)
    if not basic.is_valid:
        return basic

    exe = dafny_path or _find_dafny()
    if exe is None:
        logger.warning("Dafny CLI not found; returning basic syntax check result only.")
        return VerificationResult(
            is_valid=True,
            errors=[],
            dafny_output=None,
            verification_passed=False,
        )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".dfy", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [exe, "verify", tmp_path],
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = (result.stdout or "") + (result.stderr or "")
        logger.debug("Dafny verify output:\n%s", output)

        if result.returncode == 0:
            return VerificationResult(
                is_valid=True,
                errors=[],
                dafny_output=output,
                verification_passed=True,
            )
        else:
            errors = [line.strip() for line in output.splitlines() if line.strip()]
            if not errors:
                errors = ["Dafny verification failed with no error messages."]
            return VerificationResult(
                is_valid=False,
                errors=errors,
                dafny_output=output,
                verification_passed=False,
            )
    except subprocess.TimeoutExpired:
        return VerificationResult(
            is_valid=False,
            errors=["Dafny verification timed out."],
            dafny_output=None,
            verification_passed=False,
        )
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
