from .base import ConnectorHealth, IntelligenceAdapter


class ForecastAdapter(IntelligenceAdapter):
    key = "forecasts"
    label = "Federal Procurement Forecasts"

    def health(self, probe: bool = False) -> ConnectorHealth:
        return ConnectorHealth(
            key=self.key,
            label=self.label,
            configured=True,
            reachable=None,
            status="healthy",
            detail="Official Acquisition.gov forecast directory and agency sources.",
            official_url="https://www.acquisition.gov/procurement-forecasts",
            authentication="No API key",
        )
