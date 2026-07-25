from rest_framework import serializers

from .models import (
    Agency,
    Award,
    Category,
    Contact,
    ContactGroup,
    DataSyncRun,
    FileRecord,
    Opportunity,
    Organization,
    Participant,
    PipelineItem,
    Pursuit,
    SavedSearch,
    Task,
    TeamingRequest,
    Vendor,
)


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class OpportunitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Opportunity
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class PipelineItemSerializer(serializers.ModelSerializer):
    opportunity_detail = OpportunitySerializer(source="opportunity", read_only=True)

    class Meta:
        model = PipelineItem
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class PursuitSerializer(serializers.ModelSerializer):
    opportunity_detail = OpportunitySerializer(source="opportunity", read_only=True)

    class Meta:
        model = Pursuit
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class SavedSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedSearch
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class DataSyncRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataSyncRun
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at", "started_at", "finished_at")


class AgencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Agency
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class AwardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Award
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class ContactGroupSerializer(serializers.ModelSerializer):
    contact_count = serializers.IntegerField(source="contacts.count", read_only=True)

    class Meta:
        model = ContactGroup
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class TeamingRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamingRequest
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class FileRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileRecord
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class ParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Participant
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")
