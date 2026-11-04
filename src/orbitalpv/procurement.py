"""Public API for evidence-labeled array procurement trade studies."""

from space_pv_analytics.procurement import (
    ArrayOffer,
    ArraySizing,
    break_even_cost_m2,
    size_array,
)
from space_pv_connectors.procurement import load_array_offers

__all__ = [
    "ArrayOffer",
    "ArraySizing",
    "break_even_cost_m2",
    "load_array_offers",
    "size_array",
]
