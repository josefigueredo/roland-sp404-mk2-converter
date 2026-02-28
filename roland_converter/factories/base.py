"""SourceFactory protocol: the interface all source factories must implement."""

from typing import Protocol
from pathlib import Path

from ..scanner import SampleCandidate
from ..categorizer import CategorizedSample


class SourceFactory(Protocol):
    """Interface for source-specific scanning, categorizing, and naming."""

    def scan(self, source_path: Path) -> list[SampleCandidate]:
        """Find WAV files and return candidates."""
        ...

    def categorize(
        self, candidates: list[SampleCandidate], max_per_folder: int = 30
    ) -> list[CategorizedSample]:
        """Assign categories and curate."""
        ...

    def generate_name(self, candidate: SampleCandidate) -> str:
        """Generate output filename (without .WAV extension)."""
        ...
