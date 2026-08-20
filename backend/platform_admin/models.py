from django.conf import settings
from django.db import models


class PlatformAdminGrant(models.Model):
    class Role(models.TextChoices):
        CREATOR = "creator", "ForgeGov Creator / Platform Owner"
        SUPER_ADMIN = "super_admin", "Platform Super Admin"
        SUPPORT_ADMIN = "support_admin", "Platform Support Admin"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forgegov_platform_admin_grant",
    )
    role = models.CharField(max_length=32, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    mfa_verified = models.BooleanField(
        default=False,
        help_text="Administrative access remains denied until an MFA enrollment/verification workflow marks this grant verified.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="forgegov_platform_admin_grants_created",
    )

    def __str__(self):
        return f"{self.user} — {self.get_role_display()}"


class OrganizationControlState(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending Review"
        APPROVED = "approved", "Approved"
        ACTIVE = "active", "Active"
        REJECTED = "rejected", "Rejected"
        SUSPENDED = "suspended", "Suspended"
        DISABLED = "disabled", "Disabled"

    organization = models.OneToOneField(
        "core.Organization",
        on_delete=models.CASCADE,
        related_name="platform_control",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    beta_access = models.BooleanField(default=False)
    internal_notes = models.TextField(blank=True)
    suspension_reason = models.TextField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="forgegov_organizations_approved",
    )
    last_reviewed_at = models.DateTimeField(null=True, blank=True)
    last_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="forgegov_organizations_reviewed",
    )
    updated_at = models.DateTimeField(auto_now=True)


class UserControlState(models.Model):
    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        DISABLED = "disabled", "Disabled"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forgegov_platform_control",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    reason = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="forgegov_user_states_updated",
    )


class BetaApplication(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending Review"
        NEEDS_INFO = "needs_info", "Request Information"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    organization = models.OneToOneField(
        "core.Organization",
        on_delete=models.CASCADE,
        related_name="beta_application",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    applicant_email = models.EmailField(blank=True)
    application_notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    requested_information = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="forgegov_beta_applications_reviewed",
    )


class FeatureFlag(models.Model):
    key = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    enabled = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="forgegov_feature_flags_updated",
    )

    def __str__(self):
        return self.key


class PlatformSetting(models.Model):
    key = models.CharField(max_length=80, unique=True)
    value = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="forgegov_platform_settings_updated",
    )


class PlatformAuditEvent(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="forgegov_platform_audit_events",
    )
    action = models.CharField(max_length=120)
    target_type = models.CharField(max_length=80, blank=True)
    target_id = models.CharField(max_length=120, blank=True)
    organization = models.ForeignKey(
        "core.Organization",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="platform_audit_events",
    )
    reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["action"]),
            models.Index(fields=["target_type", "target_id"]),
        ]
