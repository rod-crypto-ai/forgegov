from __future__ import annotations

from .base import IntelligenceAdapter
from .forecasts import ForecastAdapter
from .sam import SamAdapter
from .subnet import SubnetAdapter
from .usaspending import UsaSpendingAdapter


connector_registry: tuple[IntelligenceAdapter, ...] = (
    SamAdapter(),
    UsaSpendingAdapter(),
    SubnetAdapter(),
    ForecastAdapter(),
)
