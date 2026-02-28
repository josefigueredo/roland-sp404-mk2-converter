"""Generate SP-404 compatible filenames: max 20 chars, UPPERCASE, no spaces."""

import re

from .config import Config
from .scanner import SampleCandidate

MAX_NAME_LENGTH = 20  # Excluding .WAV extension

# Regex for non-alphanumeric/underscore characters
_NON_ALNUM_RE = re.compile(r"[^A-Z0-9_]")
_MULTI_UNDERSCORE_RE = re.compile(r"_{2,}")
_TRAILING_NUM_RE = re.compile(r"[_\s](\d{1,2})$")


class NameRegistry:
    """Track all generated names per output folder to prevent collisions."""

    def __init__(self):
        self._names: dict[str, dict[str, str]] = {}  # folder -> {name -> source}

    def register(self, folder: str, name: str, source: str) -> str:
        """Register a name in a folder, resolve collisions, return final name."""
        if folder not in self._names:
            self._names[folder] = {}

        folder_names = self._names[folder]
        final = name

        if final in folder_names and folder_names[final] != source:
            # Collision - append suffix
            for i in range(2, 100):
                suffix = f"_{i}"
                # Make room for suffix
                max_base = MAX_NAME_LENGTH - len(suffix)
                candidate = final[:max_base] + suffix
                if candidate not in folder_names:
                    final = candidate
                    break

        folder_names[final] = source
        return final


def generate_name(candidate: SampleCandidate, config: Config) -> str:
    """Generate a short, meaningful filename for the SP-404 MkII.

    Returns the name WITHOUT .WAV extension.
    """
    if candidate.pack_type == "drum":
        return _generate_drum_name(candidate, config)
    else:
        return _generate_synth_name(candidate, config)


def _generate_drum_name(candidate: SampleCandidate, config: Config) -> str:
    """Generate name for a drum sample.

    Input:  'BD A 808 Decay A 01.wav'
    Output: 'BD_A_DK_A_01'
    """
    stem = candidate.filename.rsplit(".", 1)[0]
    name = stem.upper()

    # Strip machine-specific words (already in folder path)
    name = _strip_words(name, config.strip_words)

    # Also strip the machine_id from the name (e.g. "808" from "BD A 808 DECAY A 01")
    name = _strip_words(name, [candidate.machine_id.upper()])

    # Apply abbreviations
    name = _apply_abbreviations(name, config.abbreviations)

    # Clean up
    name = _NON_ALNUM_RE.sub("_", name)
    name = _MULTI_UNDERSCORE_RE.sub("_", name)
    name = name.strip("_")

    # Truncate preserving trailing number
    name = _truncate_preserving_number(name, MAX_NAME_LENGTH)

    return name


def _generate_synth_name(candidate: SampleCandidate, config: Config) -> str:
    """Generate name for a synth sample.

    Input:  '024 Buzzard Junos C0.wav'
    Output: 'BUZZARD_C0'

    Input:  'Cheeky Junos Am7.wav'
    Output: 'CHEEKY_AM7'
    """
    stem = candidate.filename.rsplit(".", 1)[0]
    name = stem.upper()

    # Strip leading MIDI note number prefix (e.g. "024 ")
    name = re.sub(r"^\d{2,3}\s+", "", name)

    # Strip machine-specific words
    name = _strip_words(name, config.strip_words)
    name = _strip_words(name, [candidate.machine_id.upper()])

    # Clean up
    name = _NON_ALNUM_RE.sub("_", name)
    name = _MULTI_UNDERSCORE_RE.sub("_", name)
    name = name.strip("_")

    # Truncate
    name = _truncate_preserving_number(name, MAX_NAME_LENGTH)

    return name if name else "SAMPLE"


def _strip_words(name: str, words: list[str]) -> str:
    """Remove specific words from the name."""
    for word in words:
        # Word boundary-aware removal
        pattern = r"\b" + re.escape(word) + r"\b"
        name = re.sub(pattern, "", name, flags=re.IGNORECASE)
    return name


def _apply_abbreviations(name: str, abbreviations: dict[str, str]) -> str:
    """Apply abbreviation map, longest matches first."""
    # Sort by key length descending so longer matches take priority
    for long_form, short_form in sorted(
        abbreviations.items(), key=lambda x: len(x[0]), reverse=True
    ):
        pattern = r"\b" + re.escape(long_form) + r"\b"
        name = re.sub(pattern, short_form, name, flags=re.IGNORECASE)
    return name


def _truncate_preserving_number(name: str, max_len: int) -> str:
    """Truncate name to max_len, preserving trailing number if present.

    'BD_A_LONG_DECAY_A_01' at max 15 -> 'BD_A_LG_DK_A_01'
    """
    if len(name) <= max_len:
        return name

    # Check for trailing number
    match = _TRAILING_NUM_RE.search(name)
    if match:
        suffix = name[match.start():]  # e.g. "_01"
        base = name[:match.start()]
        max_base = max_len - len(suffix)
        if max_base > 0:
            return base[:max_base].rstrip("_") + suffix

    return name[:max_len].rstrip("_")
