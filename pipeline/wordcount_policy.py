"""Shared source-aware article length policy for generation and quality checks."""
from __future__ import annotations

STANDARD_BANDS = {"easy": (140, 270), "middle": (300, 410)}
STANDARD_REPAIR_TARGETS = {"easy": (150, 250), "middle": (320, 380)}

# A 250–349-word Fun source can support a complete, shorter retelling without
# asking the model to pad its middle-school version beyond the source's facts.
SHORT_FUN_BANDS = {"easy": (120, 220), "middle": (250, 350)}
SHORT_FUN_TARGETS = {"easy": (135, 185), "middle": (265, 315)}


def is_short_fun_source(category: str | None, source_word_count: int | None) -> bool:
    try:
        count = int(source_word_count or 0)
    except (TypeError, ValueError):
        return False
    return category == "Fun" and 250 <= count < 350


def body_band(level: str, *, category: str | None = None,
              source_word_count: int | None = None) -> tuple[int, int]:
    bands = SHORT_FUN_BANDS if is_short_fun_source(category, source_word_count) else STANDARD_BANDS
    return bands[level]


def repair_target(level: str, *, category: str | None = None,
                  source_word_count: int | None = None) -> tuple[int, int]:
    targets = SHORT_FUN_TARGETS if is_short_fun_source(category, source_word_count) else STANDARD_REPAIR_TARGETS
    return targets[level]
