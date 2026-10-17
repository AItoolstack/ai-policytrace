"""Guards on the shipped configuration."""
from pathlib import Path

import yaml

_SETTINGS = Path(__file__).resolve().parent.parent / "config" / "settings.yaml"


def test_debug_artifacts_are_off_by_default():
    """Debug artifacts include unmasked document text, so they must be opt-in."""
    cfg = yaml.safe_load(_SETTINGS.read_text(encoding="utf-8"))
    assert cfg["debug"]["enabled"] is False
