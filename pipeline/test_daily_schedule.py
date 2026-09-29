"""Keep the production schedule Eastern, off-peak, and PR-managed."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DAILY = (ROOT / ".github/workflows/daily-pipeline.yml").read_text()
DIGEST = (ROOT / ".github/workflows/quality-digest.yml").read_text()
ADMIN = (ROOT / "website/admin.html").read_text()


def test_daily_schedule_is_0610_eastern_year_round():
    assert 'cron: "10 6 * * *"' in DAILY
    assert 'timezone: "America/New_York"' in DAILY
    eastern = ZoneInfo("America/New_York")
    assert datetime(2026, 9, 28, 6, 10, tzinfo=eastern).astimezone(ZoneInfo("UTC")).hour == 10
    assert datetime(2026, 12, 28, 6, 10, tzinfo=eastern).astimezone(ZoneInfo("UTC")).hour == 11


def test_digest_cannot_revert_schedule_with_direct_main_push():
    assert "Sync admin cron config to YAML" not in DIGEST
    assert "git push" not in DIGEST
    assert "contents: write" not in DIGEST


def test_admin_keeps_switches_but_cannot_write_legacy_utc_cron():
    assert "Runs daily at 06:10 Eastern (EST/EDT)" in ADMIN
    assert "pipeline_variant: cfg.pipeline_variant" in ADMIN
    assert "enabled: cfg.enabled" in ADMIN
    assert "cron_expression: cfg.cron_expression.trim()" not in ADMIN
