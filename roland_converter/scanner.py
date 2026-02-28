"""File discovery: traverse packs, find WAV files, yield SampleCandidate objects."""

import re
from dataclasses import dataclass
from pathlib import Path

from .config import Config, PackConfig


@dataclass
class SampleCandidate:
    source_path: Path
    pack_name: str
    machine_id: str
    pack_type: str            # "drum" or "synth"
    category_hint: str        # Extracted from path, e.g. "Bass Drum", "Keys"
    sub_category_hint: str    # e.g. "Clean", "Color", or ""
    filename: str
    pitch: str | None = None  # e.g. "C3" for synth multi-samples
    midi_note: int | None = None


# Pattern to strip leading number prefix like "01. " or "02 - "
_NUM_PREFIX_RE = re.compile(r"^\d+[\.\-\s]+\s*")

# Pitch detection: "024 Buzzard Junos C0.wav" or "Mini_3StackBass_A#-1.wav"
_PITCH_RE = re.compile(r"[A-G][#b]?-?\d$")
_MIDI_PREFIX_RE = re.compile(r"^(\d{2,3})\s+")

# Representative note names for synth filtering
_NOTE_NAMES = {
    "C0": 12, "C1": 24, "C2": 36, "C3": 48, "C4": 60, "C5": 72, "C6": 84,
    "C#0": 13, "C#1": 25, "C#2": 37, "C#3": 49, "C#4": 61,
    "D0": 14, "D1": 26, "D2": 38, "D3": 50, "D4": 62,
    "D#0": 15, "D#1": 27, "D#2": 39, "D#3": 51, "D#4": 63,
    "E0": 16, "E1": 28, "E2": 40, "E3": 52, "E4": 64,
    "F0": 17, "F1": 29, "F2": 41, "F3": 53, "F4": 65,
    "F#0": 18, "F#1": 30, "F#2": 42, "F#3": 54, "F#4": 66,
    "G0": 19, "G1": 31, "G2": 43, "G3": 55, "G4": 67,
    "G#0": 20, "G#1": 32, "G#2": 44, "G#3": 56, "G#4": 68,
    "A0": 21, "A1": 33, "A2": 45, "A3": 57, "A4": 69,
    "A#0": 22, "A#1": 34, "A#2": 46, "A#3": 58, "A#4": 70,
    "B0": 23, "B1": 35, "B2": 47, "B3": 59, "B4": 71,
    # Negative octaves
    "C-1": 0, "C#-1": 1, "D-1": 2, "D#-1": 3, "E-1": 4,
    "F-1": 5, "F#-1": 6, "G-1": 7, "G#-1": 8, "A-1": 9,
    "A#-1": 10, "B-1": 11,
}


def scan_pack(config: Config, pack: PackConfig) -> list[SampleCandidate]:
    """Scan a single pack directory for WAV files."""
    pack_dir = config.source_root / pack.pack
    if not pack_dir.exists():
        return []

    # Find the WAV subdirectory
    wav_dir = _find_wav_dir(pack_dir, config.wav_subdir_patterns)
    if wav_dir is None:
        return []

    skip_dirs_lower = {d.lower() for d in config.skip_dirs}
    skip_exts = set(config.skip_extensions)
    candidates = []

    for wav_path in wav_dir.rglob("*.wav"):
        # Skip files in excluded directories
        if _in_skip_dir(wav_path, wav_dir, skip_dirs_lower):
            continue

        # Skip companion files
        if wav_path.suffix.lower() in skip_exts:
            continue

        # Parse path to extract category info
        rel_parts = wav_path.relative_to(wav_dir).parts
        if pack.type == "drum":
            candidate = _parse_drum_candidate(wav_path, rel_parts, pack)
        else:
            candidate = _parse_synth_candidate(wav_path, rel_parts, pack)

        if candidate:
            candidates.append(candidate)

    return candidates


def _find_wav_dir(pack_dir: Path, patterns: list[str]) -> Path | None:
    """Find the WAV subdirectory within a pack."""
    for pattern in patterns:
        wav_dir = pack_dir / pattern
        if wav_dir.exists() and wav_dir.is_dir():
            return wav_dir
    return None


def _in_skip_dir(path: Path, root: Path, skip_dirs_lower: set[str]) -> bool:
    """Check if path is inside a directory that should be skipped."""
    rel = path.relative_to(root)
    for part in rel.parts[:-1]:  # Exclude filename
        if part.lower() in skip_dirs_lower:
            return True
        # Also skip "Kits" directories (pre-made kits)
        stripped = _NUM_PREFIX_RE.sub("", part)
        if stripped.lower() in ("kits", "drum loops", "loops"):
            return True
    return False


def _parse_drum_candidate(
    wav_path: Path, rel_parts: tuple[str, ...], pack: PackConfig
) -> SampleCandidate | None:
    """Parse a drum pack WAV path into a SampleCandidate.

    Typical structure: 01. Bass Drum / Clean / Digital / A / BD A 808 Decay A 01.wav
    """
    category_hint = ""
    sub_category_hint = ""

    for part in rel_parts[:-1]:
        stripped = _NUM_PREFIX_RE.sub("", part)
        if not category_hint:
            category_hint = stripped
        elif stripped.lower() in ("clean", "color", "original", "re-pitched",
                                   "analog", "digital", "tape", "saturated"):
            sub_category_hint = stripped
            break

    return SampleCandidate(
        source_path=wav_path,
        pack_name=pack.pack,
        machine_id=pack.machine_id,
        pack_type=pack.type,
        category_hint=category_hint,
        sub_category_hint=sub_category_hint,
        filename=wav_path.name,
    )


def _parse_synth_candidate(
    wav_path: Path, rel_parts: tuple[str, ...], pack: PackConfig
) -> SampleCandidate | None:
    """Parse a synth pack WAV path into a SampleCandidate.

    Typical structure: 01. Keys / PatchName / 024 Buzzard Junos C0.wav
    """
    category_hint = ""
    for part in rel_parts[:-1]:
        stripped = _NUM_PREFIX_RE.sub("", part)
        if not category_hint:
            category_hint = stripped

    # Detect pitch from filename
    stem = wav_path.stem
    pitch = None
    midi_note = None

    # Check for MIDI note prefix: "024 Buzzard Junos C0"
    midi_match = _MIDI_PREFIX_RE.match(stem)
    if midi_match:
        midi_note = int(midi_match.group(1))

    # Check for pitch suffix: ends with note like "C0", "A#-1", "F#3"
    pitch_match = _PITCH_RE.search(stem)
    if pitch_match:
        pitch = pitch_match.group(0)
        if pitch in _NOTE_NAMES and midi_note is None:
            midi_note = _NOTE_NAMES[pitch]

    return SampleCandidate(
        source_path=wav_path,
        pack_name=pack.pack,
        machine_id=pack.machine_id,
        pack_type=pack.type,
        category_hint=category_hint,
        sub_category_hint="",
        filename=wav_path.name,
        pitch=pitch,
        midi_note=midi_note,
    )


def scan_all(config: Config, packs: list[PackConfig]) -> list[SampleCandidate]:
    """Scan all selected packs and return combined candidates."""
    all_candidates = []
    for pack in packs:
        all_candidates.extend(scan_pack(config, pack))
    return all_candidates
