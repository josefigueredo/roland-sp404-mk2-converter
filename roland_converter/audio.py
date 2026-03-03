"""Audio analysis and format conversion. Source files are NEVER modified."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf


@dataclass
class AudioResult:
    passed: bool
    skip_reason: str | None      # "silent", "too_short", "error", None
    trimmed_data: np.ndarray | None
    sample_rate: int
    original_duration_ms: float
    trimmed_duration_ms: float
    original_size_bytes: int
    channels: int = 1
    subtype: str = ""             # e.g. "PCM_16", "PCM_24"


def analyze_and_process(
    path: Path,
    silence_threshold_db: float = -60.0,
    trim: bool = True,
    keep_stereo: bool = False,
) -> AudioResult:
    """Read, analyze, and process a WAV file. Returns processed audio data.

    IMPORTANT: This function only READS the source file. It never writes to it.

    Args:
        trim: If True, trim leading/trailing silence (default for one-shots).
        keep_stereo: If True, preserve stereo channels (useful for melodies/loops).
    """
    original_size = path.stat().st_size

    try:
        info = sf.info(path)
        original_channels = info.channels
        original_subtype = info.subtype
        data, sr = sf.read(path, dtype="float64")
    except Exception as e:
        return AudioResult(
            passed=False,
            skip_reason=f"error: {e}",
            trimmed_data=None,
            sample_rate=0,
            original_duration_ms=0,
            trimmed_duration_ms=0,
            original_size_bytes=original_size,
        )

    n_frames = data.shape[0] if data.ndim == 2 else len(data)
    original_duration_ms = (n_frames / sr) * 1000

    # For silence detection, use a mono mix regardless of output format
    mono = data.mean(axis=1) if data.ndim == 2 else data

    # Check if entirely silent
    if _is_silent(mono, silence_threshold_db):
        return AudioResult(
            passed=False,
            skip_reason="silent",
            trimmed_data=None,
            sample_rate=sr,
            original_duration_ms=original_duration_ms,
            trimmed_duration_ms=0,
            original_size_bytes=original_size,
            channels=original_channels,
            subtype=original_subtype,
        )

    # Convert stereo to mono unless keep_stereo is requested
    if data.ndim == 2 and not keep_stereo:
        data = mono

    # Trim leading/trailing silence
    if trim:
        data = _trim_silence(data, sr, silence_threshold_db)

    n_frames_out = data.shape[0] if data.ndim == 2 else len(data)
    trimmed_duration_ms = (n_frames_out / sr) * 1000

    return AudioResult(
        passed=True,
        skip_reason=None,
        trimmed_data=data,
        sample_rate=sr,
        original_duration_ms=original_duration_ms,
        trimmed_duration_ms=trimmed_duration_ms,
        original_size_bytes=original_size,
        channels=original_channels,
        subtype=original_subtype,
    )


def convert_and_write(
    data: np.ndarray,
    source_sr: int,
    output_path: Path,
    target_sr: int = 48000,
) -> int:
    """Convert audio to 16-bit/48kHz mono WAV and write to output_path.

    Returns the output file size in bytes.
    """
    # Resample if needed
    if source_sr != target_sr:
        data = _resample(data, source_sr, target_sr)

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write as 16-bit WAV
    sf.write(str(output_path), data, target_sr, subtype="PCM_16")

    return output_path.stat().st_size


def _is_silent(data: np.ndarray, threshold_db: float) -> bool:
    """Check if the entire file is below the silence threshold."""
    threshold_linear = 10 ** (threshold_db / 20.0)
    return float(np.max(np.abs(data))) < threshold_linear


def _trim_silence(
    data: np.ndarray,
    sr: int,
    threshold_db: float,
    padding_ms: float = 5.0,
) -> np.ndarray:
    """Remove leading and trailing silence, keeping a small padding."""
    threshold_linear = 10 ** (threshold_db / 20.0)
    padding_samples = int(sr * padding_ms / 1000)

    # Use mono mix for threshold detection on stereo data
    mono = data.mean(axis=1) if data.ndim == 2 else data
    above = np.where(np.abs(mono) > threshold_linear)[0]
    if len(above) == 0:
        return data  # Will be caught by silence detection

    n_frames = data.shape[0] if data.ndim == 2 else len(data)
    start = max(0, above[0] - padding_samples)
    end = min(n_frames, above[-1] + 1 + padding_samples)
    return data[start:end]


def _resample(data: np.ndarray, source_sr: int, target_sr: int) -> np.ndarray:
    """Resample audio using linear interpolation.

    Handles both mono (1D) and stereo (2D: frames x channels) arrays.
    """
    if source_sr == target_sr:
        return data

    ratio = target_sr / source_sr

    if data.ndim == 2:
        n_frames = data.shape[0]
        n_out = int(n_frames * ratio)
        indices = np.linspace(0, n_frames - 1, n_out)
        x = np.arange(n_frames)
        return np.column_stack([
            np.interp(indices, x, data[:, ch])
            for ch in range(data.shape[1])
        ])

    n_samples = int(len(data) * ratio)
    indices = np.linspace(0, len(data) - 1, n_samples)
    return np.interp(indices, np.arange(len(data)), data)
