"""Configuration loader for RolandConverter."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class PackConfig:
    pack: str        # Folder name on disk, e.g. "808 From Mars"
    machine_id: str  # Short ID, e.g. "808"
    type: str        # "drum" or "synth"
    tier: int


@dataclass
class Config:
    source_root: Path
    target_root: str
    wav_subdir_patterns: list[str]
    synth_representative_notes: list[str]
    skip_extensions: list[str]
    skip_dirs: list[str]
    packs: list[PackConfig]
    drum_category_map: dict[str, str]
    synth_category_map: dict[str, str]
    abbreviations: dict[str, str]
    strip_words: list[str]


def load_config(config_path: str | Path) -> Config:
    """Load configuration from YAML file."""
    config_path = Path(config_path)
    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    packs = []
    for tier_num, tier_packs in raw.get("tiers", {}).items():
        for p in tier_packs:
            packs.append(PackConfig(
                pack=p["pack"],
                machine_id=p["machine_id"],
                type=p["type"],
                tier=int(tier_num),
            ))

    return Config(
        source_root=Path(raw["source_root"]),
        target_root=raw["target_root"],
        wav_subdir_patterns=raw.get("wav_subdir_patterns", ["WAV"]),
        synth_representative_notes=raw.get("synth_representative_notes", ["C2", "C3", "C4"]),
        skip_extensions=[e.lower() for e in raw.get("skip_extensions", [])],
        skip_dirs=raw.get("skip_dirs", []),
        packs=packs,
        drum_category_map=raw.get("drum_category_map", {}),
        synth_category_map=raw.get("synth_category_map", {}),
        abbreviations=raw.get("abbreviations", {}),
        strip_words=raw.get("strip_words", []),
    )


def get_packs_for_tiers(config: Config, tiers: list[int]) -> list[PackConfig]:
    """Filter packs by selected tiers."""
    return [p for p in config.packs if p.tier in tiers]


def get_packs_by_name(config: Config, names: list[str]) -> list[PackConfig]:
    """Filter packs by name (case-insensitive partial match)."""
    results = []
    for p in config.packs:
        for name in names:
            if name.lower() in p.pack.lower():
                results.append(p)
                break
    return results
