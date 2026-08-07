"""Low-level subprocess helper used by all check functions."""
import subprocess


def run(*args: str, timeout: int = 15) -> tuple[int, str, str]:
    """Run a command; return (returncode, stdout, stderr). Never raises."""
    try:
        r = subprocess.run(
            list(args), capture_output=True, text=True, timeout=timeout
        )
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 1, "", f"timeout after {timeout}s"
    except Exception as exc:
        return 1, "", str(exc)
