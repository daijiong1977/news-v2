"""Keep the retired Fun feed out of seed replays."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def test_swimswam_seed_is_disabled():
    seed = (ROOT / "supabase/seeds/2026-05-04-cadence-seed.sql").read_text()
    assert re.search(
        r"\('Fun', 'SwimSwam',\s*'https://swimswam\.com/feed/',"
        r"\s*'rss', NULL, 'full', 10, 300, 1, 2, false, false, 'live'\)",
        seed,
    )


def test_retirement_migration_targets_only_verified_row():
    migration = (ROOT / "supabase/migrations/20260928_disable_swimswam_fun.sql").read_text()
    for guard in (
        "WHERE id = 220",
        "AND category = 'Fun'",
        "AND name = 'SwimSwam'",
        "AND rss_url = 'https://swimswam.com/feed/'",
    ):
        assert guard in migration
