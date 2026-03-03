"""From Mars factory: scanning, categorizing, and naming for Sounds From Mars packs."""

from pathlib import Path

from ..config import Config, PackConfig
from ..scanner import SampleCandidate, scan_all
from ..categorizer import CategorizedSample, GroupBy, categorize_all
from ..renamer import generate_name as _generate_name


class FromMarsFactory:
    """Source factory for the Sounds From Mars sample library."""

    def __init__(self, config: Config, packs: list[PackConfig], group_by: GroupBy = "type"):
        self.config = config
        self.packs = packs
        self.group_by = group_by

    def scan(self, source_path: Path) -> list[SampleCandidate]:
        """Scan From Mars packs for WAV files."""
        return scan_all(self.config, self.packs)

    def categorize(
        self, candidates: list[SampleCandidate], max_per_folder: int = 30
    ) -> list[CategorizedSample]:
        """Categorize using From Mars drum/synth category maps and round-robin dedup."""
        return categorize_all(candidates, self.config, max_per_folder, self.group_by)

    def generate_name(self, candidate: SampleCandidate) -> str:
        """Generate name stripping From Mars branding and applying abbreviations."""
        return _generate_name(candidate, self.config)
