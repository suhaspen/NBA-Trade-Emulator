"""
Educational aggregation rules for two-team salary matching.

The real NBA CBA depends on exact team salary, apron flags, exceptions, BYC,
S&T poison pills, and step-wise multi-team accounting. These bands are
**approximate pedagogical defaults** so you can stress-test deals by apron tier.

References for deeper modeling: official CBA text, team cap sheets, analyst tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Bracket = Literal["below_first_apron", "first_apron", "second_apron"]


@dataclass(frozen=True)
class AggregationBand:
    """Outgoing salary allowed vs incoming (simplified single ratio + cushion)."""

    multiplier: float
    cushion_mm: float
    short_label: str
    explanation: str


# Tunable defaults — adjust if you calibrate to a specific CBA article / season.
BRACKETS: dict[str, AggregationBand] = {
    "below_first_apron": AggregationBand(
        multiplier=1.25,
        cushion_mm=0.1,
        short_label="Below first apron",
        explanation=(
            "Uses a 125% + $0.1M style ceiling on outgoing vs incoming salary "
            "(loosest of the three presets)."
        ),
    ),
    "first_apron": AggregationBand(
        multiplier=1.15,
        cushion_mm=0.1,
        short_label="First apron (tight)",
        explanation=(
            "Tighter than sub-apron math — mirrors directionally that first-apron teams "
            "face extra restrictions (still not a full apron simulation)."
        ),
    ),
    "second_apron": AggregationBand(
        multiplier=1.10,
        cushion_mm=0.05,
        short_label="Second apron (strict)",
        explanation=(
            "Strictest preset — high-payroll clubs often face near dollar-for-dollar "
            "constraints in reality; this is a coarse lower bound on flexibility."
        ),
    ),
}


def get_band(key: str | None) -> AggregationBand:
    if not key or key not in BRACKETS:
        return BRACKETS["below_first_apron"]
    return BRACKETS[key]


def max_outgoing_mm(incoming_mm: float, bracket: str | None) -> tuple[float, AggregationBand]:
    b = get_band(bracket)
    return incoming_mm * b.multiplier + b.cushion_mm, b


def side_is_legal(
    outgoing_mm: float, incoming_mm: float, bracket: str | None
) -> tuple[bool, float, AggregationBand]:
    mx, b = max_outgoing_mm(incoming_mm, bracket)
    return outgoing_mm <= mx + 1e-6, mx, b
