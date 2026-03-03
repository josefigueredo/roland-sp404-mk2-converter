"""Generic factory: scan, categorize, and name any WAV folder by filename keywords."""

import re
from collections import defaultdict
from pathlib import Path

from ..scanner import SampleCandidate
from ..categorizer import CategorizedSample, GroupBy, build_output_category

# Directories to skip when scanning
_SKIP_DIRS = {
    "__macosx", ".git", ".svn", "ableton live", "kontakt", "logic exs",
    "fl studio", "reason", "maschine", "battery", ".ds_store",
}

# Keyword patterns for instrument detection (checked against filename + parent folder)
# Order matters: more specific patterns first
_KEYWORD_RULES: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"\bopen\s*h(?:i\s*)?hat\b", re.I), "HiHat Open", "HIHATS/OPEN"),
    (re.compile(r"\bclosed?\s*h(?:i\s*)?hat\b", re.I), "HiHat Closed", "HIHATS/CLOSED"),
    (re.compile(r"\bop(?:en)?[\s_]*hh\b", re.I), "HiHat Open", "HIHATS/OPEN"),
    (re.compile(r"\bcl(?:osed?)?[\s_]*hh\b", re.I), "HiHat Closed", "HIHATS/CLOSED"),
    (re.compile(r"\b(?:hi\s*hat|hh|hat)\b", re.I), "HiHat", "HIHATS"),
    (re.compile(r"\b(?:kick|bd|bass\s*drum)\b", re.I), "Kick", "KICKS"),
    (re.compile(r"\b(?:snare|sd|snr)\b", re.I), "Snare", "SNARES"),
    (re.compile(r"\bcrash\d?\b", re.I), "Crash", "CYMBALS"),
    (re.compile(r"\bride\d?\b", re.I), "Ride", "CYMBALS"),
    (re.compile(r"\b(?:cymbal|cym)\b", re.I), "Cymbal", "CYMBALS"),
    (re.compile(r"\b(?:tom|toms)\b", re.I), "Tom", "TOMS"),
    (re.compile(r"\b(?:clap|cp)\b", re.I), "Clap", "CLAPS"),
    (re.compile(r"\b(?:rim\s*shot|rim|rs)\b", re.I), "Rim", "PERCUSSION"),
    (re.compile(r"\b(?:cowbell|cb)\b", re.I), "Cowbell", "PERCUSSION"),
    (re.compile(r"\b(?:tamb(?:ourine)?)\b", re.I), "Tambourine", "PERCUSSION"),
    (re.compile(r"\b(?:shaker|shk)\b", re.I), "Shaker", "PERCUSSION"),
    (re.compile(r"\b(?:conga|cga)\b", re.I), "Conga", "PERCUSSION"),
    (re.compile(r"\b(?:bongo)\b", re.I), "Bongo", "PERCUSSION"),
    (re.compile(r"\b(?:claves?|clv)\b", re.I), "Claves", "PERCUSSION"),
    (re.compile(r"\b(?:perc(?:ussion)?)\b", re.I), "Percussion", "PERCUSSION"),
]

# Abbreviations for generic renaming
_ABBREVIATIONS = {
    "BASS DRUM": "BD",
    "KICK": "BD",
    "SNARE DRUM": "SN",
    "SNARE": "SN",
    "HI HAT": "HH",
    "HIHAT": "HH",
    "CLOSED": "CL",
    "OPEN": "OP",
    "TOM": "TM",
    "CYMBAL": "CYM",
    "COWBELL": "CB",
    "RIMSHOT": "RIM",
    "RIM SHOT": "RIM",
    "TAMBOURINE": "TAMB",
    "SHAKER": "SHK",
    "PERCUSSION": "PRC",
    "CONGA": "CGA",
    "CLAVES": "CLV",
    "SAMPLES": "",
    "SAMPLE": "",
}

_MAX_NAME_LENGTH = 20
_NON_ALNUM_RE = re.compile(r"[^A-Z0-9_]")
_MULTI_UNDERSCORE_RE = re.compile(r"_{2,}")
_TRAILING_NUM_RE = re.compile(r"[_\s](\d{1,2})$")


class GenericFactory:
    """Source factory for any WAV folder."""

    def __init__(self, group_by: GroupBy = "type"):
        self.group_by = group_by

    def scan(self, source_path: Path) -> list[SampleCandidate]:
        """Recursively find all WAV files and detect instrument category from filenames."""
        candidates = []

        for wav_path in source_path.rglob("*.wav"):
            # Skip junk directories
            if _in_skip_dir(wav_path, source_path):
                continue

            # Detect category from filename and parent folder
            search_text = f"{wav_path.stem} {wav_path.parent.name}"
            category_hint, _ = _detect_category(search_text)

            # Derive a machine_id from the nearest meaningful parent folder
            machine_id = _derive_machine_id(wav_path, source_path)

            candidates.append(SampleCandidate(
                source_path=wav_path,
                pack_name=source_path.name,
                machine_id=machine_id,
                pack_type="drum",
                category_hint=category_hint,
                sub_category_hint="",
                filename=wav_path.name,
            ))

        return candidates

    def categorize(
        self, candidates: list[SampleCandidate], max_per_folder: int = 30
    ) -> list[CategorizedSample]:
        """Categorize by keyword-detected instrument, cap at max_per_folder."""
        categorized = []
        for c in candidates:
            search_text = f"{c.filename} {c.category_hint}"
            _, output_folder = _detect_category(search_text)
            output_category = build_output_category(output_folder, c.machine_id, self.group_by)

            categorized.append(CategorizedSample(
                candidate=c,
                output_category=output_category,
                priority=1,
            ))

        # Group by category, sort alphabetically, select top N
        by_category: dict[str, list[CategorizedSample]] = defaultdict(list)
        for s in categorized:
            by_category[s.output_category].append(s)

        for cat_samples in by_category.values():
            cat_samples.sort(key=lambda s: s.candidate.filename.lower())
            for s in cat_samples[:max_per_folder]:
                s.is_selected = True

        return categorized

    def generate_name(self, candidate: SampleCandidate) -> str:
        """Generate a clean UPPERCASE name from the original filename."""
        stem = candidate.filename.rsplit(".", 1)[0]
        name = stem.upper()

        # Apply abbreviations (longest first)
        for long_form, short_form in sorted(
            _ABBREVIATIONS.items(), key=lambda x: len(x[0]), reverse=True
        ):
            pattern = r"\b" + re.escape(long_form) + r"\b"
            name = re.sub(pattern, short_form, name, flags=re.IGNORECASE)

        # Clean up
        name = _NON_ALNUM_RE.sub("_", name)
        name = _MULTI_UNDERSCORE_RE.sub("_", name)
        name = name.strip("_")

        # Truncate preserving trailing number
        name = _truncate_preserving_number(name, _MAX_NAME_LENGTH)

        return name if name else "SAMPLE"


def _in_skip_dir(path: Path, root: Path) -> bool:
    """Check if path is inside a directory that should be skipped."""
    rel = path.relative_to(root)
    for part in rel.parts[:-1]:
        if part.lower() in _SKIP_DIRS:
            return True
    return False


def _detect_category(text: str) -> tuple[str, str]:
    """Detect instrument category from text. Returns (category_hint, output_folder)."""
    # Normalize separators so word boundaries work: Clap_Soul -> Clap Soul
    normalized = re.sub(r"[_\-]", " ", text)
    for pattern, hint, folder in _KEYWORD_RULES:
        if pattern.search(normalized):
            return hint, folder
    return "MISC", "MISC"


def _derive_machine_id(wav_path: Path, source_root: Path) -> str:
    """Derive a short machine_id from the folder structure.

    Uses the first meaningful subfolder under source_root, cleaned up.
    E.g. "BATTERY__DryDrums_Bundle" -> "DRYDRUMS"
    """
    try:
        rel = wav_path.relative_to(source_root)
    except ValueError:
        return "GENERIC"

    parts = rel.parts[:-1]  # Exclude filename
    if not parts:
        return "GENERIC"

    # Use the first subfolder as the machine_id
    raw = parts[0]

    # Clean: remove common prefixes like "BATTERY__", "NI_"
    cleaned = re.sub(r"^[A-Z]+[_]{1,2}", "", raw, flags=re.IGNORECASE)
    if not cleaned:
        cleaned = raw

    # Remove common suffixes
    cleaned = re.sub(r"[_\s]*(Bundle|Pack|Kit|Samples?|Collection)$", "", cleaned, flags=re.IGNORECASE)

    # Uppercase, replace non-alnum with underscore, truncate
    cleaned = cleaned.upper()
    cleaned = _NON_ALNUM_RE.sub("_", cleaned)
    cleaned = _MULTI_UNDERSCORE_RE.sub("_", cleaned).strip("_")

    # Truncate machine_id to keep folder paths reasonable
    if len(cleaned) > 12:
        cleaned = cleaned[:12].rstrip("_")

    return cleaned if cleaned else "GENERIC"


def _truncate_preserving_number(name: str, max_len: int) -> str:
    """Truncate name to max_len, preserving trailing number if present."""
    if len(name) <= max_len:
        return name

    match = _TRAILING_NUM_RE.search(name)
    if match:
        suffix = name[match.start():]
        base = name[:match.start()]
        max_base = max_len - len(suffix)
        if max_base > 0:
            return base[:max_base].rstrip("_") + suffix

    return name[:max_len].rstrip("_")
