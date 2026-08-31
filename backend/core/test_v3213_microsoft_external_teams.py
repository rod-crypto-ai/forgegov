from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase
from .microsoft_graph import list_channels, list_teams

class MicrosoftExternalTeamsV3213Tests(SimpleTestCase):
    def row(self):
        return SimpleNamespace(external_account_id="user-1",access_token_encrypted="token")

    @patch("core.microsoft_graph.graph_request")
    def test_associated_teams_includes_shared_host(self,graph):
        def reply(row,method,path,*args,**kwargs):
            if path=="/me/joinedTeams": return {"value":[{"id":"direct","displayName":"Direct Team","tenantId":"home"}]}
            if path=="/me/teamwork/associatedTeams": return {"value":[{"id":"direct","displayName":"Direct Team","tenantId":"home"},{"id":"shared-host","displayName":"Partner Host","tenantId":"partner"}]}
            raise AssertionError(path)
        graph.side_effect=reply
        rows={x["id"]:x for x in list_teams(self.row())}
        self.assertEqual(rows["direct"]["access_type"],"direct")
        self.assertEqual(rows["shared-host"]["access_type"],"shared_channel_host")

    @patch("core.microsoft_graph._forgegov_token_tenant_id",return_value="home")
    @patch("core.microsoft_graph.graph_request")
    def test_shared_channels_are_access_filtered(self,graph,tenant):
        def reply(row,method,path,*args,**kwargs):
            if path=="/me/joinedTeams": return {"value":[]}
            if path.startswith("/teams/shared-host/allChannels"): return {"value":[{"id":"allowed","displayName":"Partner Capture","membershipType":"shared","tenantId":"partner","isArchived":False},{"id":"hidden","displayName":"Hidden","membershipType":"standard","tenantId":"partner","isArchived":False}]}
            if "allowed" in path and "doesUserHaveAccess" in path: return {"value":True}
            if "hidden" in path and "doesUserHaveAccess" in path: return {"value":False}
            raise AssertionError(path)
        graph.side_effect=reply
        rows=list_channels(self.row(),"shared-host")
        self.assertEqual([x["id"] for x in rows],["allowed"])
        self.assertEqual(rows[0]["membership_type"],"shared")
