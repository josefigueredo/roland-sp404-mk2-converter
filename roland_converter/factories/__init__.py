"""Factory registry for source-specific processing strategies."""

from pathlib import Path

from .base import SourceFactory
from .from_mars import FromMarsFactory
from .generic import GenericFactory

__all__ = ["SourceFactory", "FromMarsFactory", "GenericFactory", "get_factory"]


def get_factory(name: str, **kwargs) -> SourceFactory:
    """Get a factory by name.

    Args:
        name: "from-mars" or "generic"
        **kwargs: Factory-specific arguments:
            - from-mars: config (Config), packs (list[PackConfig])
            - generic: (none required)
    """
    if name == "from-mars":
        return FromMarsFactory(config=kwargs["config"], packs=kwargs["packs"])
    elif name == "generic":
        return GenericFactory()
    raise ValueError(f"Unknown factory: {name!r}. Available: from-mars, generic")
