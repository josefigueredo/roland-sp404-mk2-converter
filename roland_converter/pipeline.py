"""Main processing pipeline: scan -> categorize -> process -> write."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .analysis import AnalysisResult, analyze_music, append_analysis_to_name
from .audio import analyze_and_process, convert_and_write
from .categorizer import CategorizedSample
from .renamer import NameRegistry

if TYPE_CHECKING:
    from .factories.base import SourceFactory


@dataclass
class AuditEntry:
    original_path: str
    output_path: str     # "--" if skipped
    status: str          # "converted", "skipped: silent", "skipped: too_short", etc.
    original_size: int = 0
    output_size: int = 0
    sample_rate: int = 0
    channels: int = 0
    subtype: str = ""              # e.g. "PCM_16", "PCM_24"
    original_duration_ms: float = 0
    trimmed_duration_ms: float = 0
    trimmed_ms: float = 0         # How much silence was removed
    bpm: int | None = None
    bpm_confidence: float = 0.0
    key: str | None = None
    key_mode: str | None = None
    key_confidence: float = 0.0


@dataclass
class PipelineStats:
    files_scanned: int = 0
    files_selected: int = 0
    files_converted: int = 0
    files_skipped_silent: int = 0
    files_skipped_short: int = 0
    files_skipped_curation: int = 0
    files_skipped_error: int = 0
    bytes_source: int = 0
    bytes_output: int = 0
    audit_entries: list[AuditEntry] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)
    packs_not_found: list[str] = field(default_factory=list)


def run_pipeline(
    factory: SourceFactory,
    source_path: Path,
    output_root: Path,
    dry_run: bool = False,
    max_per_folder: int = 30,
    analyze: bool = False,
    bpm_threshold: float = 0.4,
    key_threshold: float = 0.6,
) -> PipelineStats:
    """Execute the full conversion pipeline."""
    stats = PipelineStats()
    name_registry = NameRegistry()

    # Phase 1: Scan
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]Scanning..."),
        transient=True,
    ) as progress:
        progress.add_task("scan", total=None)
        candidates = factory.scan(source_path)
        stats.files_scanned = len(candidates)

    if not candidates:
        return stats

    # Phase 2: Categorize and curate
    categorized = factory.categorize(candidates, max_per_folder)
    selected = [s for s in categorized if s.is_selected]
    stats.files_selected = len(selected)
    stats.files_skipped_curation = stats.files_scanned - len(selected)

    # Phase 3: Process each selected sample
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold green]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:
        task = progress.add_task("Processing samples", total=len(selected))

        for sample in selected:
            progress.update(task, advance=1)
            _process_sample(
                sample, factory, output_root, name_registry, stats, dry_run,
                analyze, bpm_threshold, key_threshold,
            )

    return stats


def _process_sample(
    sample: CategorizedSample,
    factory: SourceFactory,
    output_root: Path,
    name_registry: NameRegistry,
    stats: PipelineStats,
    dry_run: bool,
    analyze: bool = False,
    bpm_threshold: float = 0.4,
    key_threshold: float = 0.6,
) -> None:
    """Process a single selected sample through the audio pipeline."""
    candidate = sample.candidate
    source_path = candidate.source_path
    audio_kw = getattr(factory, "audio_kwargs", {})

    # Analyze audio first (needed before naming when --analyze is on)
    result = analyze_and_process(source_path, **audio_kw)
    stats.bytes_source += result.original_size_bytes

    if not result.passed:
        _record_skip(stats, source_path, result)
        return

    # BPM/key detection
    analysis: AnalysisResult | None = None
    if analyze and result.trimmed_data is not None:
        analysis = analyze_music(result.trimmed_data, result.sample_rate)

    # Generate output name (with optional BPM/key suffix)
    name = factory.generate_name(candidate)
    if analysis is not None:
        name = append_analysis_to_name(name, analysis, bpm_threshold, key_threshold)
    name = name_registry.register(sample.output_category, name, str(source_path))
    output_rel = Path(sample.output_category) / f"{name}.WAV"
    output_path = output_root / output_rel

    if dry_run:
        stats.files_converted += 1
        entry = _make_audit_entry(
            str(source_path), str(output_path), "would convert (dry run)", result,
        )
        _add_analysis_to_entry(entry, analysis)
        stats.audit_entries.append(entry)
        return

    # Convert and write
    try:
        output_size = convert_and_write(
            result.trimmed_data, result.sample_rate, output_path
        )
        stats.files_converted += 1
        stats.bytes_output += output_size
        entry = _make_audit_entry(
            str(source_path), str(output_path), "converted", result,
        )
        entry.output_size = output_size
        _add_analysis_to_entry(entry, analysis)
        stats.audit_entries.append(entry)
    except Exception as e:
        stats.files_skipped_error += 1
        stats.errors.append((str(source_path), str(e)))
        stats.audit_entries.append(_make_audit_entry(
            str(source_path), "--", f"error: {e}", result,
        ))


def _make_audit_entry(
    original_path: str, output_path: str, status: str, result,
) -> AuditEntry:
    """Create an AuditEntry with audio detail fields from an AudioResult."""
    return AuditEntry(
        original_path=original_path,
        output_path=output_path,
        status=status,
        original_size=result.original_size_bytes,
        sample_rate=result.sample_rate,
        channels=result.channels,
        subtype=result.subtype,
        original_duration_ms=result.original_duration_ms,
        trimmed_duration_ms=result.trimmed_duration_ms,
        trimmed_ms=result.original_duration_ms - result.trimmed_duration_ms,
    )


def _record_skip(stats: PipelineStats, source_path: Path, result) -> None:
    """Record a skipped file in stats and audit."""
    reason = result.skip_reason or "unknown"
    if "silent" in reason:
        stats.files_skipped_silent += 1
    elif "short" in reason:
        stats.files_skipped_short += 1
    else:
        stats.files_skipped_error += 1
        stats.errors.append((str(source_path), reason))

    stats.audit_entries.append(_make_audit_entry(
        str(source_path), "--", f"skipped: {reason}", result,
    ))


def _add_analysis_to_entry(entry: AuditEntry, analysis: AnalysisResult | None) -> None:
    """Copy analysis results into an audit entry."""
    if analysis is None:
        return
    entry.bpm = analysis.bpm
    entry.bpm_confidence = analysis.bpm_confidence
    entry.key = analysis.key
    entry.key_mode = analysis.mode
    entry.key_confidence = analysis.key_confidence
