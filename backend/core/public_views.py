"""Public inquiries never create identities, subscriptions, or workspace access."""
from rest_framework import serializers
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from .authentication import enforce_csrf
from .models import PublicInquiry


class InquiryThrottle(AnonRateThrottle):
    rate = "5/hour"


class InquirySerializer(serializers.ModelSerializer):
    consent = serializers.BooleanField(write_only=True)
    website = serializers.CharField(required=False, allow_blank=True, write_only=True, max_length=200)

    class Meta:
        model = PublicInquiry
        fields = ["name", "email", "company", "purpose", "message", "consent", "website"]
        extra_kwargs = {"message": {"max_length": 2000}, "company": {"required": True, "allow_blank": False}}

    def validate_consent(self, value):
        if not value:
            raise serializers.ValidationError("Acknowledge the Privacy Notice to submit your inquiry.")
        return value

    def validate_website(self, value):
        if value:
            raise serializers.ValidationError("Unable to accept this submission.")
        return value

    def create(self, validated_data):
        validated_data.pop("consent")
        validated_data.pop("website", None)
        validated_data["email"] = validated_data["email"].casefold()
        return super().create(validated_data)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([InquiryThrottle])
def public_inquiry(request):
    enforce_csrf(request)
    serializer = InquirySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    inquiry = serializer.save()
    return Response({"reference": str(inquiry.reference), "status": "received"}, status=201)
