from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import (
    Agency,
    Award,
    Category,
    Contact,
    ContactGroup,
    DataSyncRun,
    FileRecord,
    Invitation,
    IntelligenceAlert,
    Membership,
    AuditLog,
    Opportunity,
    OpportunityWorkspace,
    Organization,
    Participant,
    PipelineItem,
    Pursuit,
    SavedSearch,
    Task,
    TeamingRequest,
    TeamingActivity,
    Vendor,
    ProjectRoom,
    ProjectRoomPartner,
    ProjectRoomMember,
    ProjectRoomTask,
    ProjectRoomComment,
    ProjectRoomNote,
    ProjectRoomFile,
    ProjectRoomActivity,
    CollaborationNotification,
    AIConversation,
    AIMessage,
    OpportunityDocument,
    OpportunityDocumentChunk,
    OpportunityAnalysis,
    OrganizationProfile,
    NetworkConnection,
    ProjectRoomInvitation,
    OrganizationJoinRequest,
)
from .permissions import active_membership


def _request_organization(serializer):
    request = serializer.context.get("request")
    membership = active_membership(getattr(request, "user", None)) if request else None
    return membership.organization if membership else None


class WorkspaceRelationshipValidationMixin:
    """Prevent foreign-key and many-to-many references across workspaces."""

    workspace_foreign_keys: tuple[str, ...] = ()
    workspace_many_to_many: tuple[str, ...] = ()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        organization = getattr(self.instance, "organization", None) or _request_organization(self)
        if not organization:
            raise serializers.ValidationError("A valid workspace membership is required.")

        errors = {}
        for field_name in self.workspace_foreign_keys:
            value = attrs.get(field_name)
            if value is not None and getattr(value, "organization_id", None) != organization.id:
                errors[field_name] = "The selected record does not belong to this workspace."
        for field_name in self.workspace_many_to_many:
            values = attrs.get(field_name)
            if values is not None and any(getattr(value, "organization_id", None) != organization.id for value in values):
                errors[field_name] = "Every selected record must belong to this workspace."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class OpportunitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Opportunity
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class PipelineItemSerializer(WorkspaceRelationshipValidationMixin, serializers.ModelSerializer):
    opportunity_detail = OpportunitySerializer(source="opportunity", read_only=True)
    owner_name = serializers.SerializerMethodField()
    workspace_url = serializers.SerializerMethodField()
    project_room_name = serializers.CharField(source="project_room.name", read_only=True)
    teaming_workspace_url = serializers.SerializerMethodField()

    class Meta:
        model = PipelineItem
        fields = "__all__"
        read_only_fields = ("id", "organization", "created_at", "updated_at")

    def get_teaming_workspace_url(self, obj):
        return f"/project-rooms/{obj.project_room_id}" if obj.project_room_id else ""

    def get_owner_name(self, obj):
        if not obj.owner:
            return ""
        return obj.owner.get_full_name() or obj.owner.email or obj.owner.username

    def get_workspace_url(self, obj):
        source_id = str(obj.opportunity.source_id or "")
        if obj.opportunity.source == "grants.gov" or source_id.startswith("grants.gov:"):
            grant_id = source_id.removeprefix("grants.gov:")
            return f"/opportunities/federal-grants/{grant_id}" if grant_id else "/opportunities/federal-grants"
        if source_id:
            return f"/opportunities/federal-contracts/{source_id}"
        return f"/capture/pipelines?item={obj.pk}"

    def validate_project_room(self, value):
        if value is None:
            return value
        organization = _request_organization(self)
        if not organization or value.owner_organization_id != organization.id:
            raise serializers.ValidationError("Select a Project Room owned by this workspace.")
        return value

    def validate_owner(self, value):
        if value is None:
            return value
        membership = active_membership(self.context["request"].user)
        if not membership or not Membership.objects.filter(organization=membership.organization, user=value).exists():
            raise serializers.ValidationError("Owner must be a member of this workspace.")
        return value


class PursuitSerializer(WorkspaceRelationshipValidationMixin, serializers.ModelSerializer):
    opportunity_detail = OpportunitySerializer(source="opportunity", read_only=True)

    class Meta:
        model = Pursuit
        fields = "__all__"
        read_only_fields = ("id", "organization", "owner", "created_at", "updated_at")


class TaskSerializer(WorkspaceRelationshipValidationMixin, serializers.ModelSerializer):
    workspace_foreign_keys = ("pipeline_item",)

    class Meta:
        model = Task
        fields = "__all__"
        read_only_fields = ("id", "organization", "assigned_to", "created_at", "updated_at")


class SavedSearchSerializer(WorkspaceRelationshipValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = SavedSearch
        fields = "__all__"
        read_only_fields = ("id", "organization", "owner", "created_at", "updated_at")


class IntelligenceAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntelligenceAlert
        fields = (
            "id", "organization", "saved_search", "opportunity", "alert_type",
            "title", "summary", "source_id", "source_url", "matched_filters",
            "read", "dismissed", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "organization", "saved_search", "opportunity", "alert_type",
            "title", "summary", "source_id", "source_url", "matched_filters",
            "created_at", "updated_at",
        )


class DataSyncRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataSyncRun
        fields = "__all__"
        read_only_fields = tuple(field.name for field in DataSyncRun._meta.fields)


class AgencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Agency
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class AwardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Award
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class ContactSerializer(WorkspaceRelationshipValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = "__all__"
        read_only_fields = ("id", "organization", "relationship_owner", "created_at", "updated_at")


class ContactGroupSerializer(WorkspaceRelationshipValidationMixin, serializers.ModelSerializer):
    workspace_many_to_many = ("contacts",)
    contact_count = serializers.IntegerField(source="contacts.count", read_only=True)

    class Meta:
        model = ContactGroup
        fields = "__all__"
        read_only_fields = ("id", "organization", "created_at", "updated_at")


class TeamingRequestSerializer(WorkspaceRelationshipValidationMixin, serializers.ModelSerializer):
    workspace_foreign_keys = ("pursuit",)

    class Meta:
        model = TeamingRequest
        fields = "__all__"
        read_only_fields = ("id", "organization", "created_at", "updated_at")


class OpportunityWorkspaceSerializer(WorkspaceRelationshipValidationMixin, serializers.ModelSerializer):
    opportunity_detail = OpportunitySerializer(source="opportunity", read_only=True)

    class Meta:
        model = OpportunityWorkspace
        fields = "__all__"
        read_only_fields = ("id", "organization", "opportunity", "created_at", "updated_at")


class TeamingActivitySerializer(WorkspaceRelationshipValidationMixin, serializers.ModelSerializer):
    workspace_foreign_keys = ("teaming_request",)

    class Meta:
        model = TeamingActivity
        fields = "__all__"
        read_only_fields = ("id", "organization", "created_at", "updated_at")


class FileRecordSerializer(WorkspaceRelationshipValidationMixin, serializers.ModelSerializer):
    workspace_foreign_keys = ("pursuit",)

    class Meta:
        model = FileRecord
        fields = "__all__"
        read_only_fields = ("id", "organization", "created_at", "updated_at")


class ParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Participant
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name")
        read_only_fields = ("id", "username", "email")


class MembershipSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = Membership
        fields = ("id", "organization", "organization_name", "user", "role", "job_title", "department", "active", "created_at")
        read_only_fields = ("id", "organization", "user", "created_at")


class InvitationSerializer(serializers.ModelSerializer):
    invited_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = ("id", "organization", "email", "role", "job_title", "department", "status", "expires_at", "resend_count", "last_sent_at", "responded_at", "invited_by_name", "created_at")
        read_only_fields = ("id", "organization", "status", "expires_at", "resend_count", "last_sent_at", "responded_at", "invited_by_name", "created_at")

    def get_invited_by_name(self, obj):
        if not obj.invited_by:
            return ""
        return obj.invited_by.get_full_name() or obj.invited_by.email or obj.invited_by.username


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = ("id", "action", "object_type", "object_id", "metadata", "ip_address", "actor_name", "created_at")
        read_only_fields = fields

    def get_actor_name(self, obj):
        if not obj.actor:
            return "System"
        return obj.actor.get_full_name() or obj.actor.email or obj.actor.username


class ProjectRoomMemberSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="membership.user.id", read_only=True)
    user_name = serializers.SerializerMethodField()
    email = serializers.CharField(source="membership.user.email", read_only=True)
    job_title = serializers.CharField(source="membership.job_title", read_only=True)

    class Meta:
        model = ProjectRoomMember
        fields = ("id", "project_room", "membership", "user_id", "user_name", "email", "job_title", "role", "created_at", "updated_at")
        read_only_fields = ("id", "project_room", "user_id", "user_name", "email", "job_title", "created_at", "updated_at")

    def get_user_name(self, obj):
        user = obj.membership.user
        return user.get_full_name() or user.email or user.username


class ProjectRoomPartnerSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = ProjectRoomPartner
        fields = ("id", "project_room", "organization", "organization_name", "access_level", "can_upload", "can_comment", "can_view_pricing", "created_at", "updated_at")
        read_only_fields = ("id", "project_room", "organization_name", "created_at", "updated_at")


class ProjectRoomSerializer(serializers.ModelSerializer):
    owner_organization_name = serializers.CharField(source="owner_organization.name", read_only=True)
    opportunity_detail = OpportunitySerializer(source="opportunity", read_only=True)
    partners = ProjectRoomPartnerSerializer(many=True, read_only=True)
    linked_pipeline_items = serializers.SerializerMethodField()

    class Meta:
        model = ProjectRoom
        fields = ("id", "owner_organization", "owner_organization_name", "opportunity", "opportunity_detail", "name", "description", "status", "archived_at", "deleted_at", "created_by", "partners", "linked_pipeline_items", "created_at", "updated_at")
        read_only_fields = ("id", "owner_organization", "created_by", "archived_at", "deleted_at", "created_at", "updated_at")

    def get_linked_pipeline_items(self, obj):
        return [{"id": row.id, "title": row.opportunity.title, "stage": row.stage, "owner_name": (row.owner.get_full_name() or row.owner.email) if row.owner else "", "next_action": row.next_action, "follow_up_date": row.follow_up_date.isoformat() if row.follow_up_date else None} for row in obj.pipeline_items.select_related("opportunity", "owner").all()]


class OrganizationJoinRequestSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)
    class Meta:
        model = OrganizationJoinRequest
        fields = ("id", "organization", "organization_name", "user", "user_email", "email_domain", "requested_role", "status", "reviewed_by", "reviewed_at", "created_at")
        read_only_fields = ("id", "organization_name", "user", "user_email", "status", "reviewed_by", "reviewed_at", "created_at")


class AIMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIMessage
        fields = ("id", "role", "content", "sources", "model", "provider", "created_at")
        read_only_fields = fields


class AIConversationSerializer(serializers.ModelSerializer):
    messages = AIMessageSerializer(many=True, read_only=True)

    class Meta:
        model = AIConversation
        fields = ("id", "organization", "project_room", "opportunity", "title", "visibility", "created_by", "messages", "created_at", "updated_at")
        read_only_fields = ("id", "organization", "created_by", "messages", "created_at", "updated_at")


class OpportunityDocumentChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = OpportunityDocumentChunk
        fields = ("id", "ordinal", "page_number", "section", "text")
        read_only_fields = fields


class OpportunityDocumentSerializer(serializers.ModelSerializer):
    chunk_count = serializers.IntegerField(source="chunks.count", read_only=True)

    class Meta:
        model = OpportunityDocument
        fields = ("id", "opportunity", "project_room", "file_name", "source_url", "content_type", "checksum", "status", "page_count", "character_count", "error_message", "metadata", "chunk_count", "created_at", "updated_at")
        read_only_fields = fields


class OpportunityAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = OpportunityAnalysis
        fields = ("id", "opportunity", "project_room", "analysis_type", "content", "sources", "model", "input_fingerprint", "created_at", "updated_at")
        read_only_fields = fields


class ProjectRoomTaskSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    class Meta:
        model = ProjectRoomTask
        fields = "__all__"
        read_only_fields = ("id", "project_room", "created_by", "created_at", "updated_at")
    def get_assigned_to_name(self, obj):
        return obj.assigned_to.get_full_name() or obj.assigned_to.email if obj.assigned_to else ""
    def get_created_by_name(self, obj):
        return obj.created_by.get_full_name() or obj.created_by.email if obj.created_by else ""

class ProjectRoomCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    class Meta:
        model = ProjectRoomComment
        fields = "__all__"
        read_only_fields = ("id", "project_room", "author", "created_at", "updated_at")
    def get_author_name(self, obj):
        return obj.author.get_full_name() or obj.author.email if obj.author else "Former user"

class ProjectRoomNoteSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    class Meta:
        model = ProjectRoomNote
        fields = "__all__"
        read_only_fields = ("id", "project_room", "author", "created_at", "updated_at")
    def get_author_name(self, obj):
        return obj.author.get_full_name() or obj.author.email if obj.author else "Former user"

class ProjectRoomFileSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()
    class Meta:
        model = ProjectRoomFile
        fields = "__all__"
        read_only_fields = ("id", "project_room", "uploaded_by", "created_at", "updated_at")
    def get_uploaded_by_name(self, obj):
        return obj.uploaded_by.get_full_name() or obj.uploaded_by.email if obj.uploaded_by else "Former user"

class ProjectRoomActivitySerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()
    class Meta:
        model = ProjectRoomActivity
        fields = "__all__"
    def get_actor_name(self, obj):
        return obj.actor.get_full_name() or obj.actor.email if obj.actor else "System"

class CollaborationNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CollaborationNotification
        fields = ("id", "organization", "user", "project_room", "title", "message", "kind", "read", "link", "created_at", "updated_at")
        read_only_fields = ("id", "organization", "user", "project_room", "title", "message", "kind", "link", "created_at", "updated_at")


class OrganizationProfileSerializer(serializers.ModelSerializer):
    organization_id = serializers.IntegerField(source="organization.id", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    slug = serializers.CharField(source="organization.slug", read_only=True)
    uei = serializers.CharField(source="organization.uei", read_only=True)
    cage_code = serializers.CharField(source="organization.cage_code", read_only=True)

    class Meta:
        model = OrganizationProfile
        fields = ("id", "organization_id", "organization_name", "slug", "uei", "cage_code", "tagline", "description", "website", "city", "state", "country", "naics_codes", "psc_codes", "capabilities", "certifications", "contract_vehicles", "service_areas", "contact_email", "is_public", "accepting_partners", "verified", "created_at", "updated_at")
        read_only_fields = ("id", "organization_id", "organization_name", "slug", "uei", "cage_code", "verified", "created_at", "updated_at")


class NetworkConnectionSerializer(serializers.ModelSerializer):
    requester_name = serializers.CharField(source="requester.name", read_only=True)
    recipient_name = serializers.CharField(source="recipient.name", read_only=True)

    class Meta:
        model = NetworkConnection
        fields = ("id", "requester", "requester_name", "recipient", "recipient_name", "status", "message", "requested_by", "responded_by", "responded_at", "created_at", "updated_at")
        read_only_fields = ("id", "requester", "requester_name", "recipient_name", "status", "requested_by", "responded_by", "responded_at", "created_at", "updated_at")


class ProjectRoomInvitationSerializer(serializers.ModelSerializer):
    project_room_name = serializers.CharField(source="project_room.name", read_only=True)
    owner_organization_name = serializers.CharField(source="project_room.owner_organization.name", read_only=True)
    invited_organization_name = serializers.CharField(source="invited_organization.name", read_only=True)

    class Meta:
        model = ProjectRoomInvitation
        fields = ("id", "project_room", "project_room_name", "owner_organization_name", "invited_organization", "invited_organization_name", "status", "access_level", "can_upload", "can_comment", "can_view_pricing", "message", "expires_at", "last_sent_at", "resend_count", "invited_by", "responded_by", "responded_at", "created_at", "updated_at")
        read_only_fields = ("id", "project_room_name", "owner_organization_name", "invited_organization_name", "status", "last_sent_at", "resend_count", "invited_by", "responded_by", "responded_at", "created_at", "updated_at")
