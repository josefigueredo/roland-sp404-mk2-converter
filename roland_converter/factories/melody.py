"""Melody/loop factory: scan, categorize, and name musical WAV folders.

Unlike drum/synth factories, this factory:
- Keeps stereo audio (important for musical loops and ambiences)
- Does NOT trim silence (loops have intentional fades)
- Places all files under a BRAND/PACK output category
"""

import re
from pathlib import Path

from ..scanner import SampleCandidate
from ..categorizer import CategorizedSample

_SKIP_DIRS = {
    "__macosx", ".git", ".svn", ".ds_store",
}

_MAX_NAME_LENGTH = 20
_NON_ALNUM_RE = re.compile(r"[^A-Z0-9_]")
_MULTI_UNDERSCORE_RE = re.compile(r"_{2,}")

# Cymatics-style naming: "Cymatics - Name - 80 BPM F# Min Bass.wav"
_BRAND_PREFIX_RE = re.compile(r"^[A-Za-z]+\s*[-\u2013\u2014]\s*")
_BPM_RE = re.compile(r"(\d{2,3})\s*BPM", re.I)
_KEY_RE = re.compile(r"([A-G][#b]?)\s*(Min(?:or)?|Maj(?:or)?)", re.I)


class MelodyFactory:
    """Source factory for melody loops, ambiences, and musical content."""

    def __init__(self, brand: str, pack_name: str):
        self.brand = brand.upper()
        self.pack_name = pack_name.upper()

    @property
    def audio_kwargs(self) -> dict:
        """Audio processing options: keep stereo, skip silence trimming."""
        return {"trim": False, "keep_stereo": True}

    def scan(self, source_path: Path) -> list[SampleCandidate]:
        """Recursively find all WAV files (skips MIDI and junk)."""
        candidates = []

        for wav_path in source_path.rglob("*.wav"):
            if _in_skip_dir(wav_path, source_path):
                continue

            candidates.append(SampleCandidate(
                source_path=wav_path,
                pack_name=self.pack_name,
                machine_id=self.brand,
                pack_type="melody",
                category_hint="",
                sub_category_hint="",
                filename=wav_path.name,
            ))

        return candidates

    def categorize(
        self, candidates: list[SampleCandidate], max_per_folder: int = 200,
    ) -> list[CategorizedSample]:
        """Place all files under BRAND/PACK, select all up to max_per_folder."""
        output_category = f"{self.brand}/{self.pack_name}"
        categorized = []

        for c in candidates:
            categorized.append(CategorizedSample(
                candidate=c,
                output_category=output_category,
                priority=1,
                is_selected=True,
            ))

        # Cap if needed (sort alphabetically, deselect overflow)
        if len(categorized) > max_per_folder:
            categorized.sort(key=lambda s: s.candidate.filename.lower())
            for s in categorized[max_per_folder:]:
                s.is_selected = False

        return categorized

    def generate_name(self, candidate: SampleCandidate) -> str:
        """Generate a clean SP-404 name from a melody/loop filename.

        Handles patterns like:
          "Cymatics - Aurora - 80 BPM F# Min Bass.wav" -> "AURORA_BASS_80"
          "Cymatics - Ambience (Abandoned).wav"         -> "AMB_ABANDONED"
        """
        stem = candidate.filename.rsplit(".", 1)[0]

        # Strip brand prefix "Cymatics - " (or similar)
        name = _BRAND_PREFIX_RE.sub("", stem)

        # Handle "Ambience (Descriptor)" pattern
        amb_match = re.match(r"Ambience\s*\(([^)]+)\)", name, re.I)
        if amb_match:
            desc = amb_match.group(1).strip().upper()
            desc = _NON_ALNUM_RE.sub("_", desc)
            desc = _MULTI_UNDERSCORE_RE.sub("_", desc).strip("_")
            result = f"AMB_{desc}"
            return result[:_MAX_NAME_LENGTH] if len(result) > _MAX_NAME_LENGTH else result

        # Extract BPM and key
        bpm_match = _BPM_RE.search(name)
        bpm = bpm_match.group(1) if bpm_match else ""

        key_match = _KEY_RE.search(name)

        # Composition name: text before the "- BPM" section
        parts = re.split(r"\s*[-\u2013\u2014]\s*", name)
        comp_name = parts[0].strip() if parts else name

        # Stem type: whatever comes after the key signature (e.g. "Bass", "Piano", "★")
        stem_type = ""
        if key_match:
            after_key = name[key_match.end():].strip()
            after_key = re.sub(r"[\u2605\u2606*]", "MIX", after_key)  # ★ → MIX
            stem_type = after_key.strip()
        elif bpm_match:
            after_bpm = name[bpm_match.end():].strip()
            after_bpm = re.sub(r"[\u2605\u2606*]", "MIX", after_bpm)
            stem_type = after_bpm.strip()

        # Build: COMP_STEM_BPM
        comp = comp_name.upper()
        comp = _NON_ALNUM_RE.sub("_", comp)
        comp = _MULTI_UNDERSCORE_RE.sub("_", comp).strip("_")

        stem_part = ""
        if stem_type:
            stem_part = stem_type.upper()
            stem_part = _NON_ALNUM_RE.sub("_", stem_part)
            stem_part = _MULTI_UNDERSCORE_RE.sub("_", stem_part).strip("_")

        result_parts = [p for p in [comp, stem_part, bpm] if p]
        result = "_".join(result_parts)

        # Truncate: try dropping BPM first if too long
        if len(result) > _MAX_NAME_LENGTH and bpm:
            result_no_bpm = "_".join(p for p in [comp, stem_part] if p)
            if len(result_no_bpm) <= _MAX_NAME_LENGTH:
                result = result_no_bpm
            else:
                result = result[:_MAX_NAME_LENGTH].rstrip("_")
        elif len(result) > _MAX_NAME_LENGTH:
            result = result[:_MAX_NAME_LENGTH].rstrip("_")

        return result if result else "MELODY"


def _in_skip_dir(path: Path, root: Path) -> bool:
    """Check if path is inside a directory that should be skipped."""
    rel = path.relative_to(root)
    for part in rel.parts[:-1]:
        if part.lower() in _SKIP_DIRS:
            return True
    return False
