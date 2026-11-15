"""Local stub premium entitlement check."""

from pathlib import Path


class EntitlementError(PermissionError):
    """Raised when a premium adapter is selected without a license token."""


def is_premium_entitled(hermes_home: str | Path) -> bool:
    """Return whether the optional local license file is present and non-empty."""
    try:
        license_path = Path(hermes_home).expanduser() / "hermes_brain.license"
        return license_path.is_file() and bool(license_path.read_bytes().strip())
    except OSError:
        return False
