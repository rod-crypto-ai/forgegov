from rest_framework import serializers

from .models import DataSyncRun, Opportunity, Organization, PipelineItem, SavedSearch, Task


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
