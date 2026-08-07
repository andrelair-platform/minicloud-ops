from dataclasses import dataclass


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""

    def __str__(self) -> str:
        icon = "✓" if self.ok else "✗"
        suffix = f" ({self.detail})" if self.detail else ""
        status = "OK" if self.ok else f"FAILED{suffix}"
        return f"{self.name:<30}{icon} {status}"
