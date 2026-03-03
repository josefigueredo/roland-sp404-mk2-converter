"""Factory registry for source-specific processing strategies."""

from pathlib import Path

from ..categorizer import GroupBy
from .base import SourceFactory
from .from_mars import FromMarsFactory
from .generic import GenericFactory
from .melody import MelodyFactory

__all__ = ["SourceFactory", "FromMarsFactory", "GenericFactory", "MelodyFactory", "get_factory"]


def get_factory(name: str, **kwargs) -> SourceFactory:
    """Get a factory by name.

    Args:
        name: "from-mars", "generic", or "melody"
        **kwargs: Factory-specific arguments:
            - from-mars: config (Config), packs (list[PackConfig])
            - generic: (none required)
            - melody: brand (str), pack_name (str)
            - group_by: "type" (default) or "source" (all factories)
    """
    group_by: GroupBy = kwargs.pop("group_by", "type")
    if name == "from-mars":
        return FromMarsFactory(config=kwargs["config"], packs=kwargs["packs"], group_by=group_by)
    elif name == "generic":
        return GenericFactory(group_by=group_by)
    elif name == "melody":
        return MelodyFactory(brand=kwargs["brand"], pack_name=kwargs["pack_name"])
    raise ValueError(f"Unknown factory: {name!r}. Available: from-mars, generic, melody")
