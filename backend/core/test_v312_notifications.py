from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import (
    CollaborationNotification,
    IntelligenceAlert,
    Membership,
    NotificationDelivery,
    NotificationPreference,
    Opportunity,
    Organization,
    PipelineItem,
    ProjectRoom,
    ProjectRoomMember,
    ProjectRoomPartner,
    SourceRecordVersion,
)
from core.notifications import notify_project_room_participants
from core.tasks import (
    evaluate_deadline_alerts,
    evaluate_opportunity_change_alerts,
    send_daily_intelligence_digests,
)

User = get_user_model()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class V312NotificationTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Alert Test Co", slug="alert-test-co")
        self.user = User.objects.create_user(
            username="alerts@example.com",
            email="alerts@example.com",
            password="StrongPassphrase123!",
        )
        self.membership = Membership.objects.create(
            organization=self.org,
            user=self.user,
            role=Membership.Role.OWNER,
        )

    def test_notification_preferences_are_workspace_scoped_and_patchable(self):
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.patch(
            "/api/notifications/preferences/",
            {"daily_digest": False, "weekly_digest": True, "opportunity_changes": False},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        pref = NotificationPreference.objects.get(organization=self.org, user=self.user)
        self.assertFalse(pref.daily_digest)
        self.assertTrue(pref.weekly_digest)
        self.assertFalse(pref.opportunity_changes)

    def test_deadline_alerts_are_deduplicated_and_create_in_app_notification(self):
        opportunity = Opportunity.objects.create(
            source="sam.gov",
            source_id="v312-deadline-1",
            title="Deadline Test Opportunity",
            response_deadline=timezone.now() + timedelta(days=2),
            active=True,
        )
        PipelineItem.objects.create(organization=self.org, opportunity=opportunity)
        first = evaluate_deadline_alerts.run(organization_id=self.org.id)
        second = evaluate_deadline_alerts.run(organization_id=self.org.id)
        self.assertEqual(first["alerts_created"], 1)
        self.assertEqual(second["alerts_created"], 0)
        self.assertEqual(IntelligenceAlert.objects.filter(organization=self.org).count(), 1)
        self.assertTrue(
            CollaborationNotification.objects.filter(
                organization=self.org,
                user=self.user,
                kind="intelligence_deadline",
            ).exists()
        )

    def test_source_version_change_creates_one_deadline_change_alert(self):
        opportunity = Opportunity.objects.create(
            source="sam.gov",
            source_id="v312-change-1",
            title="Changed Opportunity",
            active=True,
        )
        PipelineItem.objects.create(organization=self.org, opportunity=opportunity)
        now = timezone.now()
        SourceRecordVersion.objects.create(
            source="sam.gov",
            record_type="opportunity.sam",
            source_id=opportunity.source_id,
            fingerprint="a" * 64,
            observed_at=now - timedelta(minutes=5),
            raw_data={"responseDeadLine": "2026-09-01T12:00:00Z", "active": True},
        )
        SourceRecordVersion.objects.create(
            source="sam.gov",
            record_type="opportunity.sam",
            source_id=opportunity.source_id,
            fingerprint="b" * 64,
            observed_at=now,
            raw_data={"responseDeadLine": "2026-09-03T12:00:00Z", "active": True},
        )
        first = evaluate_opportunity_change_alerts.run(organization_id=self.org.id)
        second = evaluate_opportunity_change_alerts.run(organization_id=self.org.id)
        self.assertEqual(first["alerts_created"], 1)
        self.assertEqual(second["alerts_created"], 0)
        alert = IntelligenceAlert.objects.get(organization=self.org)
        self.assertEqual(alert.alert_type, IntelligenceAlert.AlertType.DEADLINE_CHANGED)
        self.assertTrue(alert.event_key.startswith("source-change:v312-change-1:"))

    def test_project_room_internal_notifications_do_not_leak_to_partner(self):
        collaborator = User.objects.create_user(
            username="collab@example.com", email="collab@example.com", password="StrongPassphrase123!"
        )
        collaborator_membership = Membership.objects.create(
            organization=self.org, user=collaborator, role=Membership.Role.CONTRIBUTOR
        )
        partner_org = Organization.objects.create(name="Partner Co", slug="partner-co")
        partner = User.objects.create_user(
            username="partner@example.com", email="partner@example.com", password="StrongPassphrase123!"
        )
        Membership.objects.create(organization=partner_org, user=partner, role=Membership.Role.OWNER)
        room = ProjectRoom.objects.create(owner_organization=self.org, name="Secure Room", created_by=self.user)
        ProjectRoomMember.objects.create(project_room=room, membership=collaborator_membership, added_by=self.user)
        ProjectRoomPartner.objects.create(project_room=room, organization=partner_org, invited_by=self.user)

        shared = notify_project_room_participants(
            room=room,
            actor=self.user,
            title="Shared update",
            message="Shared",
            visibility="shared",
        )
        self.assertEqual(len(shared), 2)
        self.assertTrue(CollaborationNotification.objects.filter(user=partner, title="Shared update").exists())

        internal = notify_project_room_participants(
            room=room,
            actor=self.user,
            title="Internal update",
            message="Internal",
            visibility="internal",
        )
        self.assertEqual(len(internal), 1)
        self.assertTrue(CollaborationNotification.objects.filter(user=collaborator, title="Internal update").exists())
        self.assertFalse(CollaborationNotification.objects.filter(user=partner, title="Internal update").exists())

    def test_daily_digest_is_tracked_and_not_resent_within_window(self):
        IntelligenceAlert.objects.create(
            organization=self.org,
            alert_type=IntelligenceAlert.AlertType.NEW_OPPORTUNITY,
            title="Digest Opportunity",
            summary="A new opportunity matched your criteria.",
            event_key="digest-test-alert",
        )
        first = send_daily_intelligence_digests.run()
        second = send_daily_intelligence_digests.run()
        self.assertEqual(first["sent"], 1)
        self.assertEqual(second["sent"], 0)
        self.assertEqual(
            NotificationDelivery.objects.filter(
                organization=self.org,
                user=self.user,
                category="daily_digest",
                status=NotificationDelivery.Status.SENT,
            ).count(),
            1,
        )
