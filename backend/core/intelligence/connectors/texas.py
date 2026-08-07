from __future__ import annotations

from typing import Any

from django.utils import timezone

from .base import ConnectorDescriptor, ProcurementConnector


class TexasSmartbuyReferenceConnector(ProcurementConnector):
    """Reference state connector.

    This adapter intentionally exposes metadata and health only until a permitted,
    documented machine-readable feed is configured. It proves the state connector
    contract without scraping or redistributing data under uncertain terms.
    """

    descriptor = ConnectorDescriptor(
        key="texas-smartbuy-reference",
        name="Texas SmartBuy Reference",
        scope="state",
        jurisdiction_code="TX",
        jurisdiction_name="Texas",
        official_url="https://www.txsmartbuy.gov/",
        documentation_url="https://www.txsmartbuy.gov/esbddetails/viewGuide",
        license_name="Source terms review required",
        authentication="Public portal; connector feed not configured",
        capabilities=["opportunities_reference", "awards_reference", "vendor_reference"],
        rate_limit="Not applicable until an approved feed is configured",
    )

    def health(self) -> dict[str, Any]:
        return {
            **self.descriptor.to_dict(),
            "configured": False,
            "reachable": None,
            "status": "connector_required",
            "detail": "Reference implementation only. Configure an approved API, export, or licensed feed before ingestion.",
            "checked_at": timezone.now().isoformat(),
        }
