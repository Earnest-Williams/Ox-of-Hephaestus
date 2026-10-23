"""Shared typed Ox contracts; G16a does not activate personality routing."""
from .personality_actions import (
    ActionTagCatalog, DispositionTags, TaggedAction, TaggedMenu, load_catalog
)

__all__ = (
    "ActionTagCatalog", "DispositionTags", "TaggedAction", "TaggedMenu", "load_catalog"
)
