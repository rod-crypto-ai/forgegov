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

    class Meta:
        model = PipelineItem
        fields = "__all__"
        read_only_fields = ("id", "organization", "owner", "created_at", "updated_at")


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
        fields = ("id", "organization", "organization_name", "user", "role", "job_title", "created_at")
        read_only_fields = ("id", "organization", "user", "created_at")


class InvitationSerializer(serializers.ModelSerializer):
    invited_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = ("id", "organization", "email", "role", "status", "expires_at", "invited_by_name", "created_at")
        read_only_fields = ("id", "organization", "status", "expires_at", "invited_by_name", "created_at")

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

    class Meta:
        model = ProjectRoom
        fields = ("id", "owner_organization", "owner_organization_name", "opportunity", "opportunity_detail", "name", "description", "status", "created_by", "partners", "created_at", "updated_at")
        read_only_fields = ("id", "owner_organization", "created_by", "created_at", "updated_at")


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
        fields = "__all__"
        read_only_fields = ("id", "organization", "user", "created_at", "updated_at")
