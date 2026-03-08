"""BPM and musical key detection using librosa."""

from dataclasses import dataclass

import librosa
import numpy as np


# Krumhansl-Kessler key profiles
_MAJOR_PROFILE = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
)
_MINOR_PROFILE = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
)
_NOTE_NAMES = ["C", "DB", "D", "EB", "E", "F", "GB", "G", "AB", "A", "BB", "B"]

MAX_NAME_LENGTH = 20


@dataclass
class AnalysisResult:
    bpm: int | None = None
    bpm_confidence: float = 0.0
    key: str | None = None        # e.g. "C", "GB", "A"
    mode: str | None = None       # "maj" or "min"
    key_confidence: float = 0.0


def detect_bpm(data: np.ndarray, sr: int) -> tuple[int | None, float]:
    """Detect BPM from audio data. Returns (bpm, confidence 0.0-1.0)."""
    mono = data.mean(axis=1) if data.ndim == 2 else data
    mono = mono.astype(np.float32)

    tempo, beat_frames = librosa.beat.beat_track(y=mono, sr=sr)
    bpm = int(round(float(tempo[0]) if hasattr(tempo, "__len__") else float(tempo)))

    if len(beat_frames) < 2:
        return None, 0.0

    # Confidence: onset strength at beat positions vs overall average
    onset_env = librosa.onset.onset_strength(y=mono, sr=sr)
    valid_frames = beat_frames[beat_frames < len(onset_env)]
    if len(valid_frames) == 0:
        return None, 0.0

    mean_beat = float(np.mean(onset_env[valid_frames]))
    mean_overall = float(np.mean(onset_env))

    if mean_overall > 0:
        confidence = min(1.0, (mean_beat / mean_overall - 1.0) / 2.0)
    else:
        confidence = 0.0

    # Penalize few beats (short file)
    if len(valid_frames) < 4:
        confidence *= 0.5

    # Penalize extreme BPM
    if bpm < 50 or bpm > 200:
        confidence *= 0.3

    return bpm, max(0.0, confidence)


def detect_key(data: np.ndarray, sr: int) -> tuple[str | None, str | None, float]:
    """Detect musical key from audio data. Returns (key, mode, confidence 0.0-1.0)."""
    mono = data.mean(axis=1) if data.ndim == 2 else data
    mono = mono.astype(np.float32)

    chroma = librosa.feature.chroma_cqt(y=mono, sr=sr)
    chroma_avg = np.mean(chroma, axis=1)  # shape: (12,)

    best_corr = -1.0
    best_key = None
    best_mode = None

    for shift in range(12):
        major_shifted = np.roll(_MAJOR_PROFILE, shift)
        minor_shifted = np.roll(_MINOR_PROFILE, shift)

        corr_major = float(np.corrcoef(chroma_avg, major_shifted)[0, 1])
        corr_minor = float(np.corrcoef(chroma_avg, minor_shifted)[0, 1])

        if corr_major > best_corr:
            best_corr = corr_major
            best_key = _NOTE_NAMES[shift]
            best_mode = "maj"
        if corr_minor > best_corr:
            best_corr = corr_minor
            best_key = _NOTE_NAMES[shift]
            best_mode = "min"

    if best_corr < 0.3:
        return None, None, 0.0

    # Map correlation 0.3-0.8 to confidence 0.0-1.0
    confidence = max(0.0, min(1.0, (best_corr - 0.3) / 0.5))
    return best_key, best_mode, confidence


def analyze_music(data: np.ndarray, sr: int) -> AnalysisResult:
    """Run BPM and key detection on audio data."""
    bpm, bpm_conf = detect_bpm(data, sr)
    key, mode, key_conf = detect_key(data, sr)

    return AnalysisResult(
        bpm=bpm,
        bpm_confidence=bpm_conf,
        key=key,
        mode=mode,
        key_confidence=key_conf,
    )


def format_analysis_suffix(
    result: AnalysisResult,
    bpm_threshold: float = 0.4,
    key_threshold: float = 0.6,
) -> str:
    """Format analysis result as filename suffix.

    Examples: '_120_AM', '_90_C', '_120', '_CM', ''
    Major = note only (_C, _GB). Minor = note + M (_CM, _GBM).
    """
    parts: list[str] = []

    if result.bpm is not None and result.bpm_confidence >= bpm_threshold:
        parts.append(str(result.bpm))

    if result.key is not None and result.key_confidence >= key_threshold:
        key_str = result.key
        if result.mode == "min":
            key_str += "M"
        parts.append(key_str)

    if parts:
        return "_" + "_".join(parts)
    return ""


def append_analysis_to_name(
    name: str,
    result: AnalysisResult,
    bpm_threshold: float = 0.4,
    key_threshold: float = 0.6,
) -> str:
    """Append BPM/key suffix to a filename, respecting the 20-char limit.

    Graduated approach:
    - Room for both -> append full suffix (_120_AM)
    - Room for one -> prefer BPM (_120)
    - <2 chars free or base would shrink below 8 -> skip
    """
    full_suffix = format_analysis_suffix(result, bpm_threshold, key_threshold)
    if not full_suffix:
        return name

    # Try full suffix
    if len(name) + len(full_suffix) <= MAX_NAME_LENGTH:
        return name + full_suffix

    # Truncate base to fit full suffix (min 8 chars for base)
    max_base = MAX_NAME_LENGTH - len(full_suffix)
    if max_base >= 8:
        return name[:max_base].rstrip("_") + full_suffix

    # Try BPM-only suffix
    bpm_suffix = ""
    if result.bpm is not None and result.bpm_confidence >= bpm_threshold:
        bpm_suffix = f"_{result.bpm}"

    if bpm_suffix:
        if len(name) + len(bpm_suffix) <= MAX_NAME_LENGTH:
            return name + bpm_suffix
        max_base = MAX_NAME_LENGTH - len(bpm_suffix)
        if max_base >= 8:
            return name[:max_base].rstrip("_") + bpm_suffix

    # Try key-only suffix
    key_suffix = ""
    if result.key is not None and result.key_confidence >= key_threshold:
        key_str = result.key
        if result.mode == "min":
            key_str += "M"
        key_suffix = f"_{key_str}"

    if key_suffix:
        if len(name) + len(key_suffix) <= MAX_NAME_LENGTH:
            return name + key_suffix
        max_base = MAX_NAME_LENGTH - len(key_suffix)
        if max_base >= 8:
            return name[:max_base].rstrip("_") + key_suffix

    # No room at all
    return name
