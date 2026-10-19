"""Guard the quality email against a fast pipeline exhausting its job timeout."""

from pathlib import Path
import re


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/quality-digest.yml"


def test_timeout_covers_trigger_anchor_and_autofix():
    content = WORKFLOW.read_text()
    timeout = re.search(r"^    timeout-minutes: (\d+)$", content, re.MULTILINE)
    anchor = re.search(r"TARGET_EPOCH=\$\(\(TRIGGER_EPOCH \+ (\d+) \* 60\)\)", content)
    assert timeout and anchor
    assert int(timeout.group(1)) >= int(anchor.group(1)) + 20


def test_autofix_installs_safety_vet_dependencies():
    content = WORKFLOW.read_text()
    requirements = (WORKFLOW.parents[2] / "requirements.txt").read_text()
    assert "python -m pipeline.autofix_apply" in content
    assert "python -m pip install -r requirements.txt" in content
    assert re.search(r"^feedparser(?:[<=>~!].*)?$", requirements, re.MULTILINE)
