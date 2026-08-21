from django.test import SimpleTestCase
from django.urls import resolve

from .integrations import _build_sam_params
from .version import VERSION


class PrivateBetaLaunchGateV310Tests(SimpleTestCase):
    def test_release_version_is_v310_or_newer(self):
        self.assertGreaterEqual(tuple(map(int, VERSION.split("."))), (3, 1, 0))

    def test_sam_state_filter_maps_to_official_state_parameter(self):
        params = _build_sam_params(state="TX", solicitation_number="W91QVN-26-R-0001", set_aside="SBA")
        self.assertEqual(params["state"], "TX")
        self.assertEqual(params["solnum"], "W91QVN-26-R-0001")
        self.assertEqual(params["typeOfSetAside"], "SBA")

    def test_launch_critical_api_routes_resolve(self):
        paths = [
            "/api/health/",
            "/api/ready/",
            "/api/auth/login/",
            "/api/auth/register/",
            "/api/auth/password-reset/request/",
            "/api/auth/password-reset/confirm/",
            "/api/auth/security/",
            "/api/auth/security/step-up/",
            "/api/governance/role-matrix/",
            "/api/workflow/saved-searches/",
            "/api/workflow/opportunity-to-pipeline/",
        ]
        for path in paths:
            with self.subTest(path=path):
                self.assertIsNotNone(resolve(path).func)
