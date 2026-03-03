"""Click CLI for RolandConverter."""

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .config import Config, load_config, get_packs_for_tiers, get_packs_by_name
from .factories import FromMarsFactory, GenericFactory
from .pipeline import run_pipeline
from .renamer import NameRegistry
from .report import print_summary, write_audit_log

# Default config path (relative to package)
_DEFAULT_CONFIG = Path(__file__).parent.parent / "config" / "packs.yaml"

_group_by_option = click.option(
    "--group-by", "-g",
    type=click.Choice(["type", "source"], case_sensitive=False),
    default="type",
    show_default=True,
    help='Folder hierarchy: "type" = TYPE/SOURCE (default), "source" = SOURCE/TYPE',
)


@click.group()
@click.option(
    "--config", "-c",
    type=click.Path(exists=True),
    default=None,
    help="Config file path (default: config/packs.yaml)",
)
@click.pass_context
def main(ctx, config):
    """RolandConverter - Prepare samples for Roland SP-404 MkII."""
    ctx.ensure_object(dict)
    config_path = config or str(_DEFAULT_CONFIG)
    ctx.obj["config"] = load_config(config_path)
    ctx.obj["console"] = Console()


@main.command()
@click.option("--tiers", "-t", default="1", help='Tiers to include: "1", "1,2", "1,2,3"')
@click.option("--packs", "-p", multiple=True, help="Specific pack names (overrides tiers)")
@click.option("--target", "-o", type=click.Path(), default=None, help="Output root directory")
@click.option("--dry-run", "-n", is_flag=True, help="Preview without writing files")
@click.option("--max-per-folder", default=30, show_default=True, help="Max samples per leaf folder")
@_group_by_option
@click.pass_context
def convert(ctx, tiers, packs, target, dry_run, max_per_folder, group_by):
    """Convert and organize Sounds From Mars samples for SP-404 MkII import."""
    config: Config = ctx.obj["config"]
    console: Console = ctx.obj["console"]

    # Select packs
    if packs:
        selected_packs = get_packs_by_name(config, list(packs))
        if not selected_packs:
            console.print("[red]No matching packs found.[/red]")
            raise SystemExit(1)
    else:
        tier_list = [int(t.strip()) for t in tiers.split(",")]
        selected_packs = get_packs_for_tiers(config, tier_list)

    # Determine output directory
    if target:
        output_root = Path(target)
    else:
        output_root = Path.cwd() / "output" / config.target_root

    console.print(f"[bold]Source:[/bold] {config.source_root}")
    console.print(f"[bold]Output:[/bold] {output_root}")
    console.print(f"[bold]Packs:[/bold] {len(selected_packs)} selected")
    if dry_run:
        console.print("[yellow]DRY RUN - no files will be written[/yellow]")
    console.print()

    # Show selected packs
    for p in selected_packs:
        console.print(f"  [dim]Tier {p.tier}[/dim] {p.pack} ({p.machine_id}, {p.type})")
    console.print()

    # Run pipeline with From Mars factory
    factory = FromMarsFactory(config=config, packs=selected_packs, group_by=group_by)
    stats = run_pipeline(
        factory=factory,
        source_path=config.source_root,
        output_root=output_root,
        dry_run=dry_run,
        max_per_folder=max_per_folder,
    )

    # Print summary
    print_summary(stats, console)

    # Write audit log
    config_summary = (
        f"- Factory: from-mars\n"
        f"- Tiers: {tiers}\n"
        f"- Packs: {', '.join(p.pack for p in selected_packs)}\n"
        f"- Group by: {group_by}\n"
        f"- Max per folder: {max_per_folder}\n"
        f"- Dry run: {dry_run}"
    )
    audit_path = write_audit_log(stats, output_root, config_summary)
    console.print(f"[dim]Audit log: {audit_path}[/dim]")


@main.command("convert-dir")
@click.argument("source_dir", type=click.Path(exists=True))
@click.option("--target", "-o", type=click.Path(), required=True, help="Output root directory")
@click.option("--dry-run", "-n", is_flag=True, help="Preview without writing files")
@click.option("--max-per-folder", default=30, show_default=True, help="Max samples per leaf folder")
@_group_by_option
@click.pass_context
def convert_dir(ctx, source_dir, target, dry_run, max_per_folder, group_by):
    """Convert any WAV folder for SP-404 MkII import (generic mode)."""
    console: Console = ctx.obj["console"]
    source_path = Path(source_dir)
    output_root = Path(target)

    console.print(f"[bold]Source:[/bold] {source_path}")
    console.print(f"[bold]Output:[/bold] {output_root}")
    console.print(f"[bold]Mode:[/bold] Generic (keyword detection)")
    if dry_run:
        console.print("[yellow]DRY RUN - no files will be written[/yellow]")
    console.print()

    # Run pipeline with generic factory
    factory = GenericFactory(group_by=group_by)
    stats = run_pipeline(
        factory=factory,
        source_path=source_path,
        output_root=output_root,
        dry_run=dry_run,
        max_per_folder=max_per_folder,
    )

    # Print summary
    print_summary(stats, console)

    # Write audit log
    config_summary = (
        f"- Factory: generic\n"
        f"- Source: {source_path}\n"
        f"- Group by: {group_by}\n"
        f"- Max per folder: {max_per_folder}\n"
        f"- Dry run: {dry_run}"
    )
    audit_path = write_audit_log(stats, output_root, config_summary)
    console.print(f"[dim]Audit log: {audit_path}[/dim]")


@main.command("list-packs")
@click.option("--tiers", "-t", default="1,2,3", help='Tiers to show: "1", "1,2", "1,2,3"')
@click.pass_context
def list_packs(ctx, tiers):
    """Show available Sounds From Mars packs and their tier assignments."""
    config: Config = ctx.obj["config"]
    console: Console = ctx.obj["console"]

    tier_list = [int(t.strip()) for t in tiers.split(",")]
    packs = get_packs_for_tiers(config, tier_list)

    table = Table(title="Available Packs")
    table.add_column("Tier", justify="center", style="bold")
    table.add_column("Pack Name")
    table.add_column("ID", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Exists", justify="center")

    for p in sorted(packs, key=lambda x: (x.tier, x.pack)):
        exists = (config.source_root / p.pack).exists()
        exists_str = "[green]yes[/green]" if exists else "[red]no[/red]"
        table.add_row(str(p.tier), p.pack, p.machine_id, p.type, exists_str)

    console.print(table)


@main.command()
@click.argument("pack_name")
@_group_by_option
@click.pass_context
def preview(ctx, pack_name, group_by):
    """Preview what files would be selected from a Sounds From Mars pack."""
    config: Config = ctx.obj["config"]
    console: Console = ctx.obj["console"]

    matched = get_packs_by_name(config, [pack_name])
    if not matched:
        console.print(f"[red]Pack not found: {pack_name}[/red]")
        raise SystemExit(1)

    pack = matched[0]
    console.print(f"[bold]Scanning:[/bold] {pack.pack} ({pack.machine_id}, {pack.type})")
    console.print()

    factory = FromMarsFactory(config=config, packs=[pack], group_by=group_by)
    candidates = factory.scan(config.source_root)
    if not candidates:
        console.print("[yellow]No WAV files found.[/yellow]")
        return

    console.print(f"Found {len(candidates)} WAV files")

    from collections import Counter

    categorized = factory.categorize(candidates)
    selected = [s for s in categorized if s.is_selected]

    cat_counts = Counter(s.output_category for s in selected)
    console.print(f"Selected {len(selected)} after curation")
    console.print()

    table = Table(title="Output Categories")
    table.add_column("Category")
    table.add_column("Count", justify="right")

    for cat, count in sorted(cat_counts.items()):
        table.add_row(cat, str(count))

    console.print(table)
    console.print()

    # Show sample name mappings
    registry = NameRegistry()
    table2 = Table(title="Sample Name Mappings (first 20)")
    table2.add_column("Original", style="dim")
    table2.add_column("Output Name", style="cyan")
    table2.add_column("Category")

    for s in selected[:20]:
        name = factory.generate_name(s.candidate)
        name = registry.register(s.output_category, name, str(s.candidate.source_path))
        table2.add_row(
            s.candidate.filename,
            f"{name}.WAV",
            s.output_category,
        )

    console.print(table2)

    if len(selected) > 20:
        console.print(f"[dim]... and {len(selected) - 20} more[/dim]")


@main.command("preview-dir")
@click.argument("source_dir", type=click.Path(exists=True))
@click.option("--max-per-folder", default=30, show_default=True, help="Max samples per leaf folder")
@_group_by_option
@click.pass_context
def preview_dir(ctx, source_dir, max_per_folder, group_by):
    """Preview what files would be selected from any WAV folder (generic mode)."""
    console: Console = ctx.obj["console"]
    source_path = Path(source_dir)

    console.print(f"[bold]Scanning:[/bold] {source_path}")
    console.print(f"[bold]Mode:[/bold] Generic (keyword detection)")
    console.print()

    factory = GenericFactory(group_by=group_by)
    candidates = factory.scan(source_path)
    if not candidates:
        console.print("[yellow]No WAV files found.[/yellow]")
        return

    console.print(f"Found {len(candidates)} WAV files")

    from collections import Counter

    categorized = factory.categorize(candidates, max_per_folder)
    selected = [s for s in categorized if s.is_selected]

    cat_counts = Counter(s.output_category for s in selected)
    console.print(f"Selected {len(selected)} after curation (max {max_per_folder}/folder)")
    console.print()

    table = Table(title="Output Categories")
    table.add_column("Category")
    table.add_column("Count", justify="right")

    for cat, count in sorted(cat_counts.items()):
        table.add_row(cat, str(count))

    console.print(table)
    console.print()

    # Show sample name mappings
    registry = NameRegistry()
    table2 = Table(title="Sample Name Mappings (first 20)")
    table2.add_column("Original", style="dim")
    table2.add_column("Output Name", style="cyan")
    table2.add_column("Category")

    for s in selected[:20]:
        name = factory.generate_name(s.candidate)
        name = registry.register(s.output_category, name, str(s.candidate.source_path))
        table2.add_row(
            s.candidate.filename,
            f"{name}.WAV",
            s.output_category,
        )

    console.print(table2)

    if len(selected) > 20:
        console.print(f"[dim]... and {len(selected) - 20} more[/dim]")


@main.command()
@click.argument("source_dir", type=click.Path(exists=True))
@click.pass_context
def scan(ctx, source_dir):
    """Scan a directory and report WAV file statistics."""
    console: Console = ctx.obj["console"]
    source = Path(source_dir)

    wav_files = list(source.rglob("*.wav"))
    console.print(f"[bold]Directory:[/bold] {source}")
    console.print(f"[bold]WAV files found:[/bold] {len(wav_files)}")

    if wav_files:
        total_size = sum(f.stat().st_size for f in wav_files)
        console.print(f"[bold]Total size:[/bold] {total_size / (1024*1024):.1f} MB")

        # Show folder distribution
        from collections import Counter
        folders = Counter(str(f.parent.relative_to(source).parts[0]) if f.parent != source else "." for f in wav_files)

        table = Table(title="Top-level folders")
        table.add_column("Folder")
        table.add_column("Files", justify="right")

        for folder, count in sorted(folders.items(), key=lambda x: -x[1])[:20]:
            table.add_row(folder, str(count))

        console.print(table)


if __name__ == "__main__":
    main()
