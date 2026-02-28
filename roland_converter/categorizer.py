"""Map samples to output categories and curate (deduplicate, limit)."""

import re
from collections import defaultdict
from dataclasses import dataclass

from .config import Config
from .scanner import SampleCandidate


@dataclass
class CategorizedSample:
    candidate: SampleCandidate
    output_category: str   # e.g. "KICKS/808"
    priority: int          # Lower = more likely to be selected
    is_selected: bool = False


# Regex to detect trailing round-robin number: " 01", " 02", "_01", etc.
_TRAILING_NUM_RE = re.compile(r"[_\s](\d{1,2})$")


def categorize(candidate: SampleCandidate, config: Config) -> CategorizedSample:
    """Assign output category and priority to a sample candidate."""
    if candidate.pack_type == "drum":
        return _categorize_drum(candidate, config)
    else:
        return _categorize_synth(candidate, config)


def _categorize_drum(candidate: SampleCandidate, config: Config) -> CategorizedSample:
    """Categorize a drum sample based on its path-derived category hint."""
    category = _lookup_category(
        candidate.category_hint, config.drum_category_map, default="PERCUSSION"
    )
    output_category = f"{category}/{candidate.machine_id}"

    # Priority: prefer Clean/Original over Color/Saturated
    priority = _drum_priority(candidate.sub_category_hint)

    return CategorizedSample(
        candidate=candidate,
        output_category=output_category,
        priority=priority,
    )


def _categorize_synth(candidate: SampleCandidate, config: Config) -> CategorizedSample:
    """Categorize a synth sample based on its path-derived category hint."""
    category = _lookup_category(
        candidate.category_hint, config.synth_category_map, default="KEYS"
    )
    output_category = f"{category}/{candidate.machine_id}"

    # Priority: representative notes (C2/C3/C4) get higher priority
    priority = _synth_priority(candidate, config.synth_representative_notes)

    return CategorizedSample(
        candidate=candidate,
        output_category=output_category,
        priority=priority,
    )


def _lookup_category(hint: str, category_map: dict[str, str], default: str) -> str:
    """Look up a category hint in the map, trying exact then substring matches."""
    if not hint:
        return default

    # Exact match
    if hint in category_map:
        return category_map[hint]

    # Case-insensitive exact match
    hint_lower = hint.lower()
    for key, value in category_map.items():
        if key.lower() == hint_lower:
            return value

    # Substring match (e.g. "Open Hi Hat" contains "Open")
    for key, value in category_map.items():
        if key.lower() in hint_lower:
            return value

    return default


def _drum_priority(sub_category: str) -> int:
    """Assign priority based on sub-category (lower = better)."""
    sub = sub_category.lower()
    if sub in ("clean", "original", ""):
        return 1
    if sub in ("digital",):
        return 2
    if sub in ("analog",):
        return 3
    if sub in ("color", "saturated", "tape"):
        return 4
    if sub in ("re-pitched",):
        return 5
    return 3


def _synth_priority(candidate: SampleCandidate, representative_notes: list[str]) -> int:
    """Assign priority for synth samples. Representative notes get priority 1."""
    if candidate.pitch is None:
        # No pitch info (chords, FX, etc.) - keep as-is
        return 1

    if candidate.pitch in representative_notes:
        return 1

    return 10  # Deprioritize non-representative notes


def curate(
    samples: list[CategorizedSample],
    max_per_folder: int = 30,
) -> list[CategorizedSample]:
    """Select the best samples per output category folder.

    For drums: deduplicate round-robins, prefer clean, cap at max_per_folder.
    For synths: filter to representative notes, keep chords/FX as-is.
    """
    # Group by output category
    by_category: dict[str, list[CategorizedSample]] = defaultdict(list)
    for s in samples:
        by_category[s.output_category].append(s)

    for category, cat_samples in by_category.items():
        if cat_samples[0].candidate.pack_type == "drum":
            _curate_drums(cat_samples, max_per_folder)
        else:
            _curate_synths(cat_samples, max_per_folder)

    return samples


def _curate_drums(samples: list[CategorizedSample], max_per_folder: int) -> None:
    """Curate drum samples: keep first round-robin, prefer lower priority."""
    # Group by round-robin base name
    groups: dict[str, list[CategorizedSample]] = defaultdict(list)
    for s in samples:
        base = _round_robin_base(s.candidate.filename)
        groups[base].append(s)

    # From each group, pick the best one (lowest priority, then first number)
    selected = []
    for base, group in groups.items():
        group.sort(key=lambda s: (s.priority, s.candidate.filename))
        selected.append(group[0])

    # Sort by priority and take top N
    selected.sort(key=lambda s: (s.priority, s.candidate.filename))
    for s in selected[:max_per_folder]:
        s.is_selected = True


def _curate_synths(samples: list[CategorizedSample], max_per_folder: int) -> None:
    """Curate synth samples: keep representative notes and one-shots."""
    # Separate multi-sampled (has pitch) from one-shots (no pitch)
    multi_sampled = [s for s in samples if s.candidate.pitch is not None]
    one_shots = [s for s in samples if s.candidate.pitch is None]

    # For multi-sampled: keep only representative notes (priority=1)
    for s in multi_sampled:
        if s.priority == 1:
            s.is_selected = True

    # One-shots (chords, FX): keep all
    for s in one_shots:
        s.is_selected = True

    # Cap if still too many
    selected = [s for s in samples if s.is_selected]
    if len(selected) > max_per_folder:
        selected.sort(key=lambda s: (s.priority, s.candidate.filename))
        # Deselect overflow
        for s in selected[max_per_folder:]:
            s.is_selected = False


def _round_robin_base(filename: str) -> str:
    """Strip trailing round-robin number to find the group base name.

    'BD A 808 Decay A 01.wav' -> 'BD A 808 Decay A'
    'BD A 808 Decay A 02.wav' -> 'BD A 808 Decay A'
    """
    stem = filename.rsplit(".", 1)[0]  # Remove extension
    return _TRAILING_NUM_RE.sub("", stem).strip()


def categorize_all(
    candidates: list[SampleCandidate],
    config: Config,
    max_per_folder: int = 30,
) -> list[CategorizedSample]:
    """Categorize all candidates and curate."""
    categorized = [categorize(c, config) for c in candidates]
    curate(categorized, max_per_folder)
    return categorized
