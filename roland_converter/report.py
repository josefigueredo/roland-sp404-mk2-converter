"""Generate summary reports and audit Markdown files."""

from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .pipeline import PipelineStats


def print_summary(stats: PipelineStats, console: Console | None = None) -> None:
    """Print a Rich-formatted summary to the console."""
    if console is None:
        console = Console()

    console.print()
    console.rule("[bold]RolandConverter Summary")
    console.print()

    # Main stats table
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Files scanned", str(stats.files_scanned))
    table.add_row("Files selected (after curation)", str(stats.files_selected))
    table.add_row("Files converted", str(stats.files_converted))
    table.add_row("Skipped (curation)", str(stats.files_skipped_curation))
    table.add_row("Skipped (silent)", str(stats.files_skipped_silent))
    table.add_row("Skipped (too short)", str(stats.files_skipped_short))
    table.add_row("Skipped (error)", str(stats.files_skipped_error))
    table.add_row("", "")
    table.add_row("Source size", _format_bytes(stats.bytes_source))
    if stats.bytes_output > 0:
        table.add_row("Output size", _format_bytes(stats.bytes_output))
        saved = stats.bytes_source - stats.bytes_output
        if saved > 0:
            table.add_row("Space saved", _format_bytes(saved))

    console.print(table)

    # Packs not found
    if stats.packs_not_found:
        console.print()
        console.print("[yellow]Packs not found on disk:[/yellow]")
        for p in stats.packs_not_found:
            console.print(f"  - {p}")

    # Errors
    if stats.errors:
        console.print()
        console.print(f"[red]Errors ({len(stats.errors)}):[/red]")
        for path, error in stats.errors[:10]:
            console.print(f"  {path}: {error}")
        if len(stats.errors) > 10:
            console.print(f"  ... and {len(stats.errors) - 10} more")

    console.print()


def write_audit_log(
    stats: PipelineStats,
    output_dir: Path,
    config_summary: str = "",
) -> Path:
    """Write a Markdown audit file mapping original -> output paths.

    Returns the path to the audit file.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    audit_path = output_dir / f"audit_{timestamp}.md"
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# RolandConverter Audit Log",
        "",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Summary",
        "",
        f"- Files scanned: {stats.files_scanned}",
        f"- Files selected: {stats.files_selected}",
        f"- Files converted: {stats.files_converted}",
        f"- Skipped (curation): {stats.files_skipped_curation}",
        f"- Skipped (silent): {stats.files_skipped_silent}",
        f"- Skipped (too short): {stats.files_skipped_short}",
        f"- Skipped (error): {stats.files_skipped_error}",
        f"- Source size: {_format_bytes(stats.bytes_source)}",
        f"- Output size: {_format_bytes(stats.bytes_output)}",
        "",
    ]

    if config_summary:
        lines.extend([
            "## Configuration",
            "",
            config_summary,
            "",
        ])

    if stats.packs_not_found:
        lines.extend([
            "## Packs Not Found",
            "",
        ])
        for p in stats.packs_not_found:
            lines.append(f"- {p}")
        lines.append("")

    # File mapping table with audio details
    lines.extend([
        "## File Mapping",
        "",
        "| Original Path | Output Path | Status | Source Format | Original Duration | Trimmed Duration | Silence Removed | Source Size | Output Size |",
        "|---------------|------------|--------|---------------|-------------------|------------------|-----------------|-------------|-------------|",
    ])

    for entry in stats.audit_entries:
        original = entry.original_path.replace("|", "\\|")
        output = entry.output_path.replace("|", "\\|")
        status = entry.status.replace("|", "\\|")

        if entry.sample_rate > 0:
            src_fmt = f"{entry.subtype} {entry.sample_rate}Hz {entry.channels}ch"
            orig_dur = f"{entry.original_duration_ms:.0f}ms"
            trim_dur = f"{entry.trimmed_duration_ms:.0f}ms" if entry.trimmed_duration_ms > 0 else "--"
            trimmed = f"{entry.trimmed_ms:.0f}ms" if entry.trimmed_ms > 0 else "0ms"
        else:
            src_fmt = "--"
            orig_dur = "--"
            trim_dur = "--"
            trimmed = "--"

        src_size = _format_bytes(entry.original_size) if entry.original_size > 0 else "--"
        out_size = _format_bytes(entry.output_size) if entry.output_size > 0 else "--"

        lines.append(
            f"| {original} | {output} | {status} "
            f"| {src_fmt} | {orig_dur} | {trim_dur} | {trimmed} | {src_size} | {out_size} |"
        )

    lines.append("")

    # Errors section
    if stats.errors:
        lines.extend([
            "## Errors",
            "",
        ])
        for path, error in stats.errors:
            lines.append(f"- `{path}`: {error}")
        lines.append("")

    audit_path.write_text("\n".join(lines), encoding="utf-8")
    return audit_path


def _format_bytes(n: int) -> str:
    """Format bytes as human-readable string."""
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{n / (1024 * 1024 * 1024):.2f} GB"
