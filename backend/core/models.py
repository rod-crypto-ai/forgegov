import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Organization(TimeStampedModel):
    class Status(models.TextChoices):
        TRIAL = "trial", "Trial"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past Due"
        SUSPENDED = "suspended", "Suspended"
        CANCELLED = "cancelled", "Cancelled"

    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    uei = models.CharField(max_length=32, blank=True)
    cage_code = models.CharField(max_length=16, blank=True)
    business_domain = models.CharField(max_length=255, blank=True, null=True, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    def __str__(self):
        return self.name


class Membership(TimeStampedModel):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Administrator"
        CAPTURE = "capture", "Capture Manager"
        BD = "bd", "Business Development"
        PROPOSAL = "proposal", "Proposal Manager"
        PRICING = "pricing", "Pricing Manager"
        CONTRIBUTOR = "contributor", "Contributor"
        VIEWER = "viewer", "Read Only"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="organization_memberships")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.VIEWER)
    job_title = models.CharField(max_length=120, blank=True)
    department = models.CharField(max_length=120, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("organization", "user"), name="unique_organization_membership"),
        ]


class UserSecurityProfile(TimeStampedModel):
    class LifecycleStatus(models.TextChoices):
        PENDING_EMAIL = "pending_email_verification", "Pending Email Verification"
        EMAIL_VERIFIED = "email_verified", "Email Verified"
        ONBOARDING = "onboarding", "Onboarding"
        PENDING_ORGANIZATION = "pending_organization", "Pending Organization Approval"
        ACTIVE = "active", "Active"

    class AccountStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        LOCKED = "locked", "Locked"
        DISABLED = "disabled", "Disabled"
        DELETION_PENDING = "deletion_pending", "Deletion Pending"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forgegov_security")
    lifecycle_status = models.CharField(max_length=40, choices=LifecycleStatus.choices, default=LifecycleStatus.PENDING_EMAIL)
    account_status = models.CharField(max_length=30, choices=AccountStatus.choices, default=AccountStatus.ACTIVE)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    terms_version = models.CharField(max_length=40, blank=True)
    privacy_accepted_at = models.DateTimeField(null=True, blank=True)
    privacy_version = models.CharField(max_length=40, blank=True)
    registration_email_domain = models.CharField(max_length=255, blank=True)
    pending_organization = models.ForeignKey(Organization, null=True, blank=True, on_delete=models.SET_NULL, related_name="pending_identity_profiles")
    last_password_change_at = models.DateTimeField(null=True, blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["user_id"]


class AccountActionToken(TimeStampedModel):
    class Purpose(models.TextChoices):
        EMAIL_VERIFICATION = "email_verification", "Email Verification"
        PASSWORD_RESET = "password_reset", "Password Reset"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forgegov_account_tokens")
    purpose = models.CharField(max_length=30, choices=Purpose.choices)
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    requested_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "purpose", "-created_at"], name="accttoken_user_purp_idx"),
            models.Index(fields=["purpose", "expires_at"], name="accttoken_purp_exp_idx"),
        ]


class OrganizationSecurityPolicy(TimeStampedModel):
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name="security_policy")
    require_mfa = models.BooleanField(default=False)
    require_mfa_for_financial_roles = models.BooleanField(default=False)
    require_mfa_for_exports = models.BooleanField(default=False)
    require_mfa_for_project_room_admin = models.BooleanField(default=False)
    session_max_days = models.PositiveSmallIntegerField(default=7)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="updated_org_security_policies")


class TOTPDevice(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="totp_device")
    name = models.CharField(max_length=120, default="Authenticator app")
    secret_encrypted = models.TextField()
    confirmed_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=False)


class RecoveryCode(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recovery_codes")
    code_hash = models.CharField(max_length=64)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [models.UniqueConstraint(fields=("user", "code_hash"), name="uniq_recovery_user_hash")]
        indexes = [models.Index(fields=["user", "used_at"], name="recovery_user_used_idx")]


class PasskeyCredential(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="passkey_credentials")
    name = models.CharField(max_length=120, default="Passkey")
    credential_id = models.TextField(unique=True)
    public_key = models.TextField()
    sign_count = models.PositiveBigIntegerField(default=0)
    transports = models.JSONField(default=list, blank=True)
    device_type = models.CharField(max_length=40, blank=True)
    backed_up = models.BooleanField(default=False)
    last_used_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "active"], name="passkey_user_active_idx")]


class AuthSession(TimeStampedModel):
    session_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forgegov_auth_sessions")
    organization = models.ForeignKey(Organization, null=True, blank=True, on_delete=models.SET_NULL, related_name="auth_sessions")
    refresh_jti = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_label = models.CharField(max_length=255, blank=True)
    expires_at = models.DateTimeField()
    last_seen_at = models.DateTimeField(default=timezone.now)
    revoked_at = models.DateTimeField(null=True, blank=True)
    step_up_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-last_seen_at", "-created_at"]
        indexes = [
            models.Index(fields=["user", "revoked_at", "-last_seen_at"], name="authsess_user_rev_idx"),
            models.Index(fields=["session_id"], name="authsess_sid_idx"),
        ]


class SecurityChallenge(TimeStampedModel):
    class Purpose(models.TextChoices):
        MFA_LOGIN = "mfa_login", "MFA Login"
        MFA_ENROLLMENT = "mfa_enrollment", "MFA Enrollment"
        WEBAUTHN_REGISTER = "webauthn_register", "WebAuthn Registration"
        WEBAUTHN_AUTH = "webauthn_auth", "WebAuthn Authentication"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="security_challenges")
    purpose = models.CharField(max_length=30, choices=Purpose.choices)
    token_hash = models.CharField(max_length=64, unique=True)
    challenge = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "purpose", "expires_at"], name="secchal_user_purp_idx")]


class Opportunity(TimeStampedModel):
    class NoticeType(models.TextChoices):
        SOLICITATION = "solicitation", "Solicitation"
        COMBINED = "combined", "Combined Synopsis / Solicitation"
        SOURCES_SOUGHT = "sources_sought", "Sources Sought"
        PRESOLICITATION = "presolicitation", "Presolicitation"
        AWARD = "award", "Award Notice"
        SPECIAL = "special", "Special Notice"
        JUSTIFICATION = "justification", "Justification"
        SURPLUS = "surplus", "Sale of Surplus Property"
        OTHER = "other", "Other"

    source = models.CharField(max_length=40, default="sam.gov")
    source_id = models.CharField(max_length=255, unique=True)
    solicitation_number = models.CharField(max_length=120, blank=True)
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    agency = models.CharField(max_length=255, blank=True)
    subagency = models.CharField(max_length=255, blank=True)
    office = models.CharField(max_length=255, blank=True)
    organization_path = models.TextField(blank=True)
    notice_type = models.CharField(max_length=40, choices=NoticeType.choices, default=NoticeType.OTHER)
    notice_type_raw = models.CharField(max_length=120, blank=True)
    naics_code = models.CharField(max_length=12, blank=True)
    psc_code = models.CharField(max_length=12, blank=True)
    set_aside = models.CharField(max_length=255, blank=True)
    set_aside_code = models.CharField(max_length=50, blank=True)
    posted_date = models.DateTimeField(null=True, blank=True)
    response_deadline = models.DateTimeField(null=True, blank=True)
    archive_date = models.DateTimeField(null=True, blank=True)
    place_of_performance = models.CharField(max_length=500, blank=True)
    active = models.BooleanField(default=True)
    source_url = models.URLField(blank=True)
    resource_links = models.JSONField(default=list, blank=True)
    source_modified_at = models.DateTimeField(null=True, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["response_deadline", "-posted_date"]
        indexes = [
            models.Index(fields=["source", "source_id"]),
            models.Index(fields=["solicitation_number"]),
            models.Index(fields=["naics_code"]),
            models.Index(fields=["psc_code"]),
            models.Index(fields=["response_deadline"]),
            models.Index(fields=["active", "posted_date"]),
        ]

    def __str__(self):
        return self.title


class PipelineItem(TimeStampedModel):
    class Stage(models.TextChoices):
        DISCOVERED = "discovered", "Discovered"
        REVIEWING = "reviewing", "Reviewing"
        QUALIFIED = "qualified", "Qualified"
        BID_DECISION = "bid_decision", "Bid / No-Bid"
        CAPTURE = "capture", "Capture Planning"
        TEAMING = "teaming", "Teaming"
        PROPOSAL = "proposal", "Proposal Development"
        SUBMITTED = "submitted", "Submitted"
        AWARDED = "awarded", "Awarded"
        LOST = "lost", "Lost"
        NO_BID = "no_bid", "No-Bid"
        ARCHIVED = "archived", "Archived"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="pipeline_items")
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name="pipeline_items")
    stage = models.CharField(max_length=30, choices=Stage.choices, default=Stage.DISCOVERED)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_pipeline_items")
    estimated_value = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    probability_of_win = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    next_action = models.CharField(max_length=500, blank=True)
    follow_up_date = models.DateField(null=True, blank=True)
    priority = models.CharField(max_length=20, default="medium")
    assigned_team = models.CharField(max_length=120, blank=True)
    project_room = models.ForeignKey("ProjectRoom", null=True, blank=True, on_delete=models.SET_NULL, related_name="pipeline_items")
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("organization", "opportunity"), name="unique_pipeline_opportunity_per_org"),
        ]


class Task(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="tasks")
    pipeline_item = models.ForeignKey(PipelineItem, null=True, blank=True, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_forgegov_tasks")
    due_at = models.DateTimeField(null=True, blank=True)
    completed = models.BooleanField(default=False)


class SavedSearch(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="saved_searches")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="forgegov_saved_searches")
    name = models.CharField(max_length=255)
    filters = models.JSONField(default=dict)
    alert_frequency = models.CharField(max_length=20, default="daily")
    enabled = models.BooleanField(default=True)


class DataSyncRun(TimeStampedModel):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        PARTIAL = "partial", "Partial"
        FAILED = "failed", "Failed"

    source = models.CharField(max_length=80)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RUNNING)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    records_received = models.PositiveIntegerField(default=0)
    records_created = models.PositiveIntegerField(default=0)
    records_updated = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    request_metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["source", "status", "-started_at"])]

    def __str__(self):
        return f"{self.source}: {self.status} ({self.started_at:%Y-%m-%d %H:%M})"


class Pursuit(TimeStampedModel):
    class Stage(models.TextChoices):
        TRIAGE = "triage", "Triage"
        QUALIFY = "qualify", "Qualify"
        BID_DECISION = "bid_decision", "Bid / No-Bid"
        CAPTURE = "capture", "Capture"
        PROPOSAL = "proposal", "Proposal"
        SUBMITTED = "submitted", "Submitted"
        AWARDED = "awarded", "Awarded"
        LOST = "lost", "Lost"
        NO_BID = "no_bid", "No-Bid"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="pursuits")
    opportunity = models.ForeignKey(Opportunity, null=True, blank=True, on_delete=models.SET_NULL, related_name="pursuits")
    title = models.CharField(max_length=500)
    stage = models.CharField(max_length=30, choices=Stage.choices, default=Stage.TRIAGE)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_pursuits")
    estimated_value = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    probability_of_win = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    due_date = models.DateTimeField(null=True, blank=True)
    next_action = models.CharField(max_length=500, blank=True)
    incumbent = models.CharField(max_length=255, blank=True)
    prime_or_sub = models.CharField(max_length=20, default="prime")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["due_date", "-updated_at"]
        indexes = [models.Index(fields=["organization", "stage"]), models.Index(fields=["due_date"])]

    def __str__(self):
        return self.title


class Agency(TimeStampedModel):
    name = models.CharField(max_length=255, unique=True)
    agency_code = models.CharField(max_length=32, blank=True)
    agency_type = models.CharField(max_length=40, default="federal")
    parent_name = models.CharField(max_length=255, blank=True)
    website = models.URLField(blank=True)
    opportunity_count = models.PositiveIntegerField(default=0)
    award_count = models.PositiveIntegerField(default=0)
    obligated_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    raw_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Vendor(TimeStampedModel):
    name = models.CharField(max_length=255)
    uei = models.CharField(max_length=32, blank=True, db_index=True)
    cage_code = models.CharField(max_length=16, blank=True, db_index=True)
    city = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=40, blank=True)
    website = models.URLField(blank=True)
    socioeconomic_statuses = models.JSONField(default=list, blank=True)
    naics_codes = models.JSONField(default=list, blank=True)
    claimed = models.BooleanField(default=False)
    award_count = models.PositiveIntegerField(default=0)
    obligated_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    raw_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["name"])]

    def __str__(self):
        return self.name


class Award(TimeStampedModel):
    class AwardType(models.TextChoices):
        CONTRACT = "contract", "Federal Contract"
        IDV = "idv", "Federal IDV"
        VEHICLE = "vehicle", "Federal Contract Vehicle"
        GRANT = "grant", "Federal Grant"
        STATE_LOCAL = "state_local", "State and Local Contract"
        STATE_LOCAL_IDV = "state_local_idv", "State and Local IDV"
        STATE_LOCAL_VEHICLE = "state_local_vehicle", "State and Local Vehicle"

    source = models.CharField(max_length=80, default="usaspending.gov")
    source_id = models.CharField(max_length=255, unique=True)
    award_number = models.CharField(max_length=160, blank=True, db_index=True)
    parent_award_number = models.CharField(max_length=160, blank=True, db_index=True)
    awarding_office = models.CharField(max_length=255, blank=True)
    funding_office = models.CharField(max_length=255, blank=True)
    recipient_cage = models.CharField(max_length=16, blank=True)
    set_aside_code = models.CharField(max_length=40, blank=True)
    jurisdiction_level = models.CharField(max_length=24, default="federal")
    jurisdiction_code = models.CharField(max_length=24, blank=True)
    source_updated_at = models.DateTimeField(null=True, blank=True)
    award_type = models.CharField(max_length=40, choices=AwardType.choices, default=AwardType.CONTRACT)
    description = models.TextField(blank=True)
    recipient_name = models.CharField(max_length=255, blank=True)
    recipient_uei = models.CharField(max_length=32, blank=True)
    awarding_agency = models.CharField(max_length=255, blank=True)
    funding_agency = models.CharField(max_length=255, blank=True)
    obligated_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    potential_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    naics_code = models.CharField(max_length=12, blank=True)
    psc_code = models.CharField(max_length=12, blank=True)
    place_of_performance = models.CharField(max_length=500, blank=True)
    source_url = models.URLField(blank=True)
    raw_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-obligated_amount", "-updated_at"]
        indexes = [models.Index(fields=["award_type", "awarding_agency"]), models.Index(fields=["recipient_name"])]

    def __str__(self):
        return self.award_number or self.source_id


class ConnectorSource(TimeStampedModel):
    class Scope(models.TextChoices):
        FEDERAL = "federal", "Federal"
        STATE = "state", "State"
        LOCAL = "local", "Local"
        COMMERCIAL = "commercial", "Commercial"

    key = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=255)
    scope = models.CharField(max_length=24, choices=Scope.choices, default=Scope.FEDERAL)
    jurisdiction_code = models.CharField(max_length=24, blank=True)
    jurisdiction_name = models.CharField(max_length=120, blank=True)
    official_url = models.URLField(blank=True)
    documentation_url = models.URLField(blank=True)
    license_name = models.CharField(max_length=160, blank=True)
    license_url = models.URLField(blank=True)
    authentication = models.CharField(max_length=160, blank=True)
    capabilities = models.JSONField(default=list, blank=True)
    enabled = models.BooleanField(default=True)
    last_status = models.CharField(max_length=40, default="not_checked")
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    record_count = models.PositiveBigIntegerField(default=0)
    rate_limit = models.CharField(max_length=120, blank=True)
    last_error = models.TextField(blank=True)

    class Meta:
        ordering = ["scope", "jurisdiction_name", "name"]

    def __str__(self):
        return self.name


class AwardSyncRun(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        PARTIAL = "partial", "Partial"

    connector_key = models.CharField(max_length=120, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    cursor = models.JSONField(default=dict, blank=True)
    pages_processed = models.PositiveIntegerField(default=0)
    records_seen = models.PositiveIntegerField(default=0)
    records_created = models.PositiveIntegerField(default=0)
    records_updated = models.PositiveIntegerField(default=0)
    errors = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-created_at"]


class SourceRecordVersion(TimeStampedModel):
    source = models.CharField(max_length=80, db_index=True)
    record_type = models.CharField(max_length=80, db_index=True)
    source_id = models.CharField(max_length=255, db_index=True)
    fingerprint = models.CharField(max_length=64, db_index=True)
    source_modified_at = models.DateTimeField(null=True, blank=True)
    observed_at = models.DateTimeField(default=timezone.now, db_index=True)
    last_seen_at = models.DateTimeField(default=timezone.now, db_index=True)
    provenance = models.JSONField(default=dict, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-observed_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=("source", "record_type", "source_id", "fingerprint"),
                name="uniq_source_record_version_fingerprint",
            ),
        ]
        indexes = [
            models.Index(fields=["source", "record_type", "source_id", "-observed_at"], name="srcver_source_record_idx"),
        ]


class SyncQuarantine(TimeStampedModel):
    source = models.CharField(max_length=80, db_index=True)
    record_type = models.CharField(max_length=80, db_index=True)
    source_id = models.CharField(max_length=255, blank=True, db_index=True)
    payload_hash = models.CharField(max_length=64, db_index=True)
    reason = models.CharField(max_length=120)
    error_message = models.CharField(max_length=1000, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    occurrences = models.PositiveIntegerField(default=1)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.CharField(max_length=1000, blank=True)
    data_sync_run = models.ForeignKey(
        DataSyncRun, null=True, blank=True, on_delete=models.SET_NULL, related_name="quarantine_records"
    )
    award_sync_run = models.ForeignKey(
        AwardSyncRun, null=True, blank=True, on_delete=models.SET_NULL, related_name="quarantine_records"
    )

    class Meta:
        ordering = ["-updated_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=("source", "record_type", "payload_hash"),
                name="uniq_quarantine_source_record_hash",
            ),
        ]
        indexes = [
            models.Index(fields=["source", "resolved_at", "-updated_at"], name="quarantine_source_state_idx"),
        ]


class Contact(TimeStampedModel):
    class ContactType(models.TextChoices):
        GOVERNMENT = "government", "Government"
        VENDOR = "vendor", "Vendor"
        PARTNER = "partner", "Partner"
        INTERNAL = "internal", "Internal"

    organization = models.ForeignKey(Organization, null=True, blank=True, on_delete=models.CASCADE, related_name="contacts")
    full_name = models.CharField(max_length=255)
    title = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=60, blank=True)
    contact_type = models.CharField(max_length=30, choices=ContactType.choices, default=ContactType.GOVERNMENT)
    agency_name = models.CharField(max_length=255, blank=True)
    vendor_name = models.CharField(max_length=255, blank=True)
    relationship_owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_contacts")
    last_contacted_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class ContactGroup(TimeStampedModel):
    organization = models.ForeignKey(Organization, null=True, blank=True, on_delete=models.CASCADE, related_name="contact_groups")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    contacts = models.ManyToManyField(Contact, blank=True, related_name="groups")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class TeamingRequest(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        OPEN = "open", "Open"
        RESPONDED = "responded", "Responded"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        CLOSED = "closed", "Closed"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="teaming_requests")
    pursuit = models.ForeignKey(Pursuit, null=True, blank=True, on_delete=models.SET_NULL, related_name="teaming_requests")
    company_name = models.CharField(max_length=255)
    role = models.CharField(max_length=30, default="subcontractor")
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT)
    capabilities = models.TextField(blank=True)
    point_of_contact = models.CharField(max_length=255, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["status", "due_date", "-updated_at"]

    def __str__(self):
        return f"{self.company_name} - {self.role}"


class OpportunityWorkspace(TimeStampedModel):
    """Persistent capture workspace attached to one opportunity and organization."""
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="opportunity_workspaces")
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name="workspaces")
    notes = models.TextField(blank=True)
    capture_summary = models.TextField(blank=True)
    risks = models.JSONField(default=list, blank=True)
    compliance_items = models.JSONField(default=list, blank=True)
    decision = models.CharField(max_length=20, default="undecided")

    class Meta:
        ordering = ["-updated_at"]
        constraints = [models.UniqueConstraint(fields=("organization", "opportunity"), name="unique_opportunity_workspace_per_org")]


class ProposalPlan(TimeStampedModel):
    class Status(models.TextChoices):
        PLANNING = "planning", "Planning"
        IN_PROGRESS = "in_progress", "In Progress"
        REVIEW = "review", "Review"
        SUBMISSION_READY = "submission_ready", "Submission Ready"
        SUBMITTED = "submitted", "Submitted"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="proposal_plans")
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name="proposal_plans")
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PLANNING)
    submission_method = models.CharField(max_length=500, blank=True)
    final_submission_verified = models.BooleanField(default=False)
    amendment_baseline = models.JSONField(default=dict, blank=True)
    amendment_checked_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_proposal_plans")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("organization", "opportunity"), name="unique_proposal_plan_per_org_opportunity"),
        ]
        indexes = [
            models.Index(fields=["organization", "status"], name="core_propplan_org_status_idx"),
        ]


class ProposalRequirement(TimeStampedModel):
    class Status(models.TextChoices):
        NEEDS_REVIEW = "needs_review", "Needs Review"
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLIANT = "compliant", "Compliant"
        NOT_APPLICABLE = "not_applicable", "Not Applicable"

    plan = models.ForeignKey(ProposalPlan, on_delete=models.CASCADE, related_name="requirements")
    key = models.CharField(max_length=160)
    requirement = models.TextField()
    source = models.CharField(max_length=500, blank=True)
    source_kind = models.CharField(max_length=80, blank=True)
    evidence = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.NEEDS_REVIEW)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_proposal_requirements")
    due_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(fields=("plan", "key"), name="unique_proposal_requirement_key"),
        ]
        indexes = [
            models.Index(fields=["plan", "status"], name="core_propreq_plan_status_idx"),
        ]


class ProposalReview(TimeStampedModel):
    class ReviewType(models.TextChoices):
        PINK = "pink", "Pink Team"
        RED = "red", "Red Team"
        GOLD = "gold", "Gold Team"
        FINAL = "final", "Final Submission Check"

    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        IN_PROGRESS = "in_progress", "In Progress"
        PASSED = "passed", "Passed"
        BLOCKED = "blocked", "Blocked"

    plan = models.ForeignKey(ProposalPlan, on_delete=models.CASCADE, related_name="reviews")
    review_type = models.CharField(max_length=20, choices=ReviewType.choices)
    target_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PLANNED)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_proposal_reviews")
    completed_at = models.DateTimeField(null=True, blank=True)
    summary = models.TextField(blank=True)

    class Meta:
        ordering = ["target_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=("plan", "review_type"), name="unique_proposal_review_type"),
        ]


class ProposalFinding(TimeStampedModel):
    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"
        ACCEPTED = "accepted", "Accepted Risk"

    plan = models.ForeignKey(ProposalPlan, on_delete=models.CASCADE, related_name="findings")
    review = models.ForeignKey(ProposalReview, null=True, blank=True, on_delete=models.CASCADE, related_name="findings")
    requirement = models.ForeignKey(ProposalRequirement, null=True, blank=True, on_delete=models.SET_NULL, related_name="findings")
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.MEDIUM)
    title = models.CharField(max_length=500)
    detail = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_proposal_findings")
    due_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_proposal_findings")

    class Meta:
        ordering = ["status", "-created_at"]
        indexes = [
            models.Index(fields=["plan", "status", "severity"], name="propfind_plan_stat_idx"),
        ]


class ProposalSubmissionSnapshot(TimeStampedModel):
    """Immutable record of what ForgeGov recorded at submission time."""

    plan = models.ForeignKey(ProposalPlan, on_delete=models.CASCADE, related_name="submission_snapshots")
    sequence = models.PositiveIntegerField(default=1)
    submitted_at = models.DateTimeField(default=timezone.now)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="proposal_submission_snapshots",
    )
    delivery_method = models.CharField(max_length=500, blank=True)
    confirmation_reference = models.CharField(max_length=500, blank=True)
    notes = models.TextField(blank=True)
    opportunity_snapshot = models.JSONField(default=dict, blank=True)
    requirement_snapshot = models.JSONField(default=list, blank=True)
    review_snapshot = models.JSONField(default=list, blank=True)
    finding_snapshot = models.JSONField(default=list, blank=True)
    file_manifest = models.JSONField(default=list, blank=True)
    amendment_snapshot = models.JSONField(default=dict, blank=True)
    snapshot_hash = models.CharField(max_length=64)

    class Meta:
        ordering = ["-submitted_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=("plan", "sequence"), name="unique_prop_submit_sequence"),
        ]
        indexes = [
            models.Index(fields=["plan", "-submitted_at"], name="propsub_plan_time_idx"),
        ]


class ProposalCloseout(TimeStampedModel):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        EVALUATION = "evaluation", "Evaluation"
        DISCUSSIONS = "discussions", "Discussions"
        FPR = "fpr", "Final Proposal Revision"
        AWARDED = "awarded", "Awarded"
        LOST = "lost", "Lost"
        CANCELLED = "cancelled", "Cancelled"

    plan = models.OneToOneField(ProposalPlan, on_delete=models.CASCADE, related_name="closeout")
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.SUBMITTED)
    awardee = models.CharField(max_length=500, blank=True)
    award_value = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    award_date = models.DateField(null=True, blank=True)
    debrief_requested = models.BooleanField(default=False)
    debrief_received = models.BooleanField(default=False)
    win_loss_reason = models.TextField(blank=True)
    customer_feedback = models.TextField(blank=True)
    strengths = models.JSONField(default=list, blank=True)
    weaknesses = models.JSONField(default=list, blank=True)
    lessons_learned = models.JSONField(default=list, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_proposal_closeouts",
    )

    class Meta:
        ordering = ["-updated_at"]


class PricingProfile(TimeStampedModel):
    """Organization-level pricing defaults reused across pursuits."""

    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name="pricing_profile")
    fringe_percent = models.DecimalField(max_digits=7, decimal_places=3, default=0)
    overhead_percent = models.DecimalField(max_digits=7, decimal_places=3, default=0)
    ga_percent = models.DecimalField(max_digits=7, decimal_places=3, default=0)
    material_handling_percent = models.DecimalField(max_digits=7, decimal_places=3, default=0)
    subcontract_handling_percent = models.DecimalField(max_digits=7, decimal_places=3, default=0)
    payroll_burden_percent = models.DecimalField(max_digits=7, decimal_places=3, default=0)
    default_profit_percent = models.DecimalField(max_digits=7, decimal_places=3, default=12)
    minimum_margin_percent = models.DecimalField(max_digits=7, decimal_places=3, default=8)
    annual_escalation_percent = models.DecimalField(max_digits=7, decimal_places=3, default=3)
    payment_lag_days = models.PositiveIntegerField(default=30)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="updated_pricing_profiles")


class PricingPlan(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEW = "review", "Ready for Review"
        APPROVED = "approved", "Approved"
        LOCKED = "locked", "Locked"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="pricing_plans")
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name="pricing_plans")
    name = models.CharField(max_length=255, default="Target Pricing")
    revision = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    fringe_percent = models.DecimalField(max_digits=7, decimal_places=3, default=0)
    overhead_percent = models.DecimalField(max_digits=7, decimal_places=3, default=0)
    ga_percent = models.DecimalField(max_digits=7, decimal_places=3, default=0)
    material_handling_percent = models.DecimalField(max_digits=7, decimal_places=3, default=0)
    subcontract_handling_percent = models.DecimalField(max_digits=7, decimal_places=3, default=0)
    payroll_burden_percent = models.DecimalField(max_digits=7, decimal_places=3, default=0)
    target_profit_percent = models.DecimalField(max_digits=7, decimal_places=3, default=12)
    minimum_margin_percent = models.DecimalField(max_digits=7, decimal_places=3, default=8)
    annual_escalation_percent = models.DecimalField(max_digits=7, decimal_places=3, default=3)
    pursuit_cost = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    performance_months = models.DecimalField(max_digits=7, decimal_places=2, default=12)
    payment_lag_days = models.PositiveIntegerField(default=30)
    mobilization_cost = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    available_working_capital = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_pricing_plans")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_pricing_plans")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("organization", "opportunity", "revision"), name="uniq_priceplan_org_opp_rev"),
        ]
        ordering = ["-revision", "-updated_at"]
        indexes = [models.Index(fields=["organization", "opportunity", "status"], name="priceplan_org_opp_stat")]


class PricingClin(TimeStampedModel):
    plan = models.ForeignKey(PricingPlan, on_delete=models.CASCADE, related_name="clins")
    clin = models.CharField(max_length=80)
    description = models.CharField(max_length=500, blank=True)
    option_year = models.PositiveSmallIntegerField(default=0)
    quantity = models.DecimalField(max_digits=18, decimal_places=3, default=1)
    unit = models.CharField(max_length=80, default="LOT")
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["option_year", "sort_order", "clin"]
        constraints = [models.UniqueConstraint(fields=("plan", "clin", "option_year"), name="uniq_priceclin_plan_clin_yr")]


class PricingCostItem(TimeStampedModel):
    class Category(models.TextChoices):
        LABOR = "labor", "Labor"
        MATERIAL = "material", "Materials"
        TRAVEL = "travel", "Travel"
        EQUIPMENT = "equipment", "Equipment"
        SUBCONTRACT = "subcontract", "Subcontractor"
        BOND = "bond", "Bond"
        INSURANCE = "insurance", "Insurance"
        OTHER = "other", "Other Direct Cost"

    plan = models.ForeignKey(PricingPlan, on_delete=models.CASCADE, related_name="cost_items")
    clin = models.ForeignKey(PricingClin, null=True, blank=True, on_delete=models.SET_NULL, related_name="cost_items")
    category = models.CharField(max_length=30, choices=Category.choices)
    name = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=18, decimal_places=3, default=1)
    unit_cost = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    labor_hours = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    labor_rate = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    option_year = models.PositiveSmallIntegerField(default=0)
    escalation_percent = models.DecimalField(max_digits=7, decimal_places=3, default=0)
    source = models.CharField(max_length=500, blank=True)
    source_kind = models.CharField(max_length=40, default="user")
    notes = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["option_year", "category", "sort_order", "id"]
        indexes = [models.Index(fields=["plan", "category", "option_year"], name="priceitem_plan_cat_yr")]


class PricingSubcontractor(TimeStampedModel):
    """Prime/subcontractor economics kept separate from raw direct-cost line items."""

    plan = models.ForeignKey(PricingPlan, on_delete=models.CASCADE, related_name="subcontractors")
    name = models.CharField(max_length=500)
    quoted_cost = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    prime_markup_percent = models.DecimalField(max_digits=7, decimal_places=3, default=0)
    management_burden = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    insurance_cost = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    contingency = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    deposit_percent = models.DecimalField(max_digits=7, decimal_places=3, default=0)
    payment_terms_days = models.PositiveIntegerField(default=30)
    monthly_burn = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    source = models.CharField(max_length=500, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name", "id"]
        indexes = [models.Index(fields=["plan", "name"], name="pricesub_plan_name_idx")]


class PricingScenario(TimeStampedModel):
    class ScenarioType(models.TextChoices):
        COMPETITIVE = "competitive", "Competitive"
        TARGET = "target", "Target"
        PROTECTIVE = "protective", "Protective"

    plan = models.ForeignKey(PricingPlan, on_delete=models.CASCADE, related_name="scenarios")
    scenario_type = models.CharField(max_length=20, choices=ScenarioType.choices)
    profit_percent = models.DecimalField(max_digits=7, decimal_places=3, default=12)
    cost_adjustment_percent = models.DecimalField(max_digits=7, decimal_places=3, default=0)
    price_adjustment_percent = models.DecimalField(max_digits=7, decimal_places=3, default=0)
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("plan", "scenario_type"), name="uniq_pricescn_plan_type")]
        ordering = ["scenario_type"]


class PriceToWinSnapshot(TimeStampedModel):
    """Evidence-backed competitive price range captured at a point in time."""

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="price_to_win_snapshots")
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name="price_to_win_snapshots")
    pricing_plan = models.ForeignKey(PricingPlan, null=True, blank=True, on_delete=models.SET_NULL, related_name="price_to_win_snapshots")
    competitive_floor = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    target_price = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    protective_ceiling = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    confidence = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    evidence_count = models.PositiveIntegerField(default=0)
    comparable_award_ids = models.JSONField(default=list, blank=True)
    assumptions = models.JSONField(default=list, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    model_inputs = models.JSONField(default=dict, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="recorded_price_to_win_snapshots")

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["organization", "opportunity", "-created_at"], name="ptw_org_opp_time_idx")]


class PortfolioSnapshot(TimeStampedModel):
    """Persistent executive portfolio rollup for trend and governance review."""

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="portfolio_snapshots")
    pipeline_value = models.DecimalField(max_digits=22, decimal_places=2, default=0)
    weighted_pipeline_value = models.DecimalField(max_digits=22, decimal_places=2, default=0)
    modeled_revenue = models.DecimalField(max_digits=22, decimal_places=2, default=0)
    projected_profit = models.DecimalField(max_digits=22, decimal_places=2, default=0)
    backlog_value = models.DecimalField(max_digits=22, decimal_places=2, default=0)
    recommended_working_capital = models.DecimalField(max_digits=22, decimal_places=2, default=0)
    working_capital_gap = models.DecimalField(max_digits=22, decimal_places=2, default=0)
    portfolio_margin_percent = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    opportunity_count = models.PositiveIntegerField(default=0)
    risk_summary = models.JSONField(default=dict, blank=True)
    agency_concentration = models.JSONField(default=list, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="recorded_portfolio_snapshots")

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["organization", "-created_at"], name="portfolio_org_time_idx")]


class PursuitDecisionSnapshot(TimeStampedModel):
    """Persistent, explainable decision record for a pursuit at a point in time."""

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="pursuit_decisions")
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name="pursuit_decisions")
    recommendation = models.CharField(max_length=40)
    win_probability = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    confidence = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    evidence_coverage = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    estimated_value = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    expected_value = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    target_margin_percent = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    pursuit_cost = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    subcontractor_share_percent = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    scorecard = models.JSONField(default=dict, blank=True)
    evidence = models.JSONField(default=list, blank=True)
    conditions = models.JSONField(default=list, blank=True)
    rationale = models.JSONField(default=list, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="recorded_pursuit_decisions")

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["organization", "opportunity", "-created_at"], name="pdec_org_opp_time_idx")]


class CompetitivePositionSnapshot(TimeStampedModel):
    """Persistent competitive-positioning record for capture reviews and trend analysis."""

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="competitive_position_snapshots")
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name="competitive_position_snapshots")
    qualification_score = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    recommendation = models.CharField(max_length=40)
    agency_profile = models.JSONField(default=dict, blank=True)
    incumbent = models.JSONField(default=dict, blank=True)
    competitors = models.JSONField(default=list, blank=True)
    win_themes = models.JSONField(default=list, blank=True)
    capture_gaps = models.JSONField(default=list, blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="recorded_competitive_position_snapshots")

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["organization", "opportunity", "-created_at"], name="cpos_org_opp_time_idx")]


class TeamingActivity(TimeStampedModel):
    class ActivityType(models.TextChoices):
        NOTE = "note", "Note"
        EMAIL = "email", "Email"
        CALL = "call", "Call"
        MEETING = "meeting", "Meeting"
        FOLLOW_UP = "follow_up", "Follow-up"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="teaming_activities")
    teaming_request = models.ForeignKey(TeamingRequest, on_delete=models.CASCADE, related_name="activities")
    activity_type = models.CharField(max_length=20, choices=ActivityType.choices, default=ActivityType.NOTE)
    subject = models.CharField(max_length=255)
    details = models.TextField(blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    follow_up_at = models.DateTimeField(null=True, blank=True)
    completed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-occurred_at", "-created_at"]


class FileRecord(TimeStampedModel):
    organization = models.ForeignKey(Organization, null=True, blank=True, on_delete=models.CASCADE, related_name="file_records")
    opportunity = models.ForeignKey(Opportunity, null=True, blank=True, on_delete=models.SET_NULL, related_name="file_records")
    pursuit = models.ForeignKey(Pursuit, null=True, blank=True, on_delete=models.SET_NULL, related_name="file_records")
    name = models.CharField(max_length=500)
    file_type = models.CharField(max_length=80, blank=True)
    source = models.CharField(max_length=40, default="user")
    source_url = models.URLField(blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    version = models.PositiveIntegerField(default=1)
    checksum = models.CharField(max_length=128, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name


class Participant(TimeStampedModel):
    class ParticipantType(models.TextChoices):
        STATE = "state", "State"
        JURISDICTION = "jurisdiction", "Jurisdiction"
        OTHER = "other", "Other"

    name = models.CharField(max_length=255)
    participant_type = models.CharField(max_length=40, choices=ParticipantType.choices, default=ParticipantType.OTHER)
    state_code = models.CharField(max_length=4, blank=True)
    website = models.URLField(blank=True)
    raw_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=("name", "participant_type"), name="unique_participant_type_name")]

    def __str__(self):
        return self.name


class Category(TimeStampedModel):
    class CategoryType(models.TextChoices):
        NAICS = "naics", "NAICS"
        PSC = "psc", "PSC"
        NIGP = "nigp", "NIGP"
        UNSPSC = "unspsc", "UNSPSC"

    code = models.CharField(max_length=40)
    category_type = models.CharField(max_length=20, choices=CategoryType.choices)
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    parent_code = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["category_type", "code"]
        constraints = [models.UniqueConstraint(fields=("category_type", "code"), name="unique_category_type_code")]

    def __str__(self):
        return f"{self.category_type.upper()} {self.code}"


class Invitation(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Cancelled"
        REVOKED = "revoked", "Revoked"
        EXPIRED = "expired", "Expired"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=Membership.Role.choices, default=Membership.Role.VIEWER)
    token = models.CharField(max_length=128, unique=True)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="sent_forgegov_invitations")
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    job_title = models.CharField(max_length=120, blank=True)
    department = models.CharField(max_length=120, blank=True)
    resend_count = models.PositiveSmallIntegerField(default=0)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="accepted_forgegov_invitations")

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=("organization", "email"), condition=models.Q(status="pending"), name="unique_pending_invitation_per_org_email"),
        ]


class AuditLog(TimeStampedModel):
    organization = models.ForeignKey(Organization, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_logs")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="forgegov_audit_logs")
    action = models.CharField(max_length=120)
    object_type = models.CharField(max_length=120, blank=True)
    object_id = models.CharField(max_length=120, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "-created_at"]), models.Index(fields=["action"])]


class IntelligenceAlert(TimeStampedModel):
    class AlertType(models.TextChoices):
        NEW_OPPORTUNITY = "new_opportunity", "New Opportunity"
        DEADLINE = "deadline", "Upcoming Deadline"
        AMENDMENT = "amendment", "Amendment Posted"
        DEADLINE_CHANGED = "deadline_changed", "Response Deadline Changed"
        CANCELLED = "cancelled", "Opportunity Cancelled"
        DOCUMENT = "document", "New Attachment"
        SET_ASIDE_CHANGED = "set_aside_changed", "Set-Aside Changed"
        STATUS_CHANGED = "status_changed", "Status Changed"
        PIPELINE = "pipeline", "Pipeline Update"
        PROJECT_ROOM = "project_room", "Project Room Update"
        AWARD = "award", "Award Intelligence"
        FORECAST = "forecast", "Forecast Update"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="intelligence_alerts")
    saved_search = models.ForeignKey(SavedSearch, null=True, blank=True, on_delete=models.SET_NULL, related_name="alerts")
    opportunity = models.ForeignKey(Opportunity, null=True, blank=True, on_delete=models.SET_NULL, related_name="alerts")
    alert_type = models.CharField(max_length=40, choices=AlertType.choices, default=AlertType.NEW_OPPORTUNITY)
    title = models.CharField(max_length=500)
    summary = models.TextField(blank=True)
    source_id = models.CharField(max_length=255, blank=True)
    source_url = models.URLField(blank=True)
    matched_filters = models.JSONField(default=dict, blank=True)
    event_key = models.CharField(max_length=255, blank=True, db_index=True)
    read = models.BooleanField(default=False)
    dismissed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "saved_search", "source_id", "alert_type"),
                name="unique_saved_search_intelligence_alert",
            ),
            models.UniqueConstraint(
                fields=("organization", "event_key"),
                condition=~models.Q(event_key=""),
                name="unique_intelligence_alert_event_key",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "read", "-created_at"], name="core_intell_organiz_3309e7_idx"),
            models.Index(fields=["source_id"], name="core_intell_source__cba733_idx"),
        ]

    def __str__(self):
        return self.title

class ProjectRoom(TimeStampedModel):
    class Status(models.TextChoices):
        PLANNING = "planning", "Planning"
        ACTIVE = "active", "Active"
        SUBMITTED = "submitted", "Submitted"
        CLOSED = "closed", "Closed"

    owner_organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="owned_project_rooms")
    opportunity = models.ForeignKey(Opportunity, null=True, blank=True, on_delete=models.SET_NULL, related_name="project_rooms")
    name = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNING)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_project_rooms")
    archived_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["owner_organization", "status", "-updated_at"], name="core_projec_owner_o_0a7332_idx")]

    def __str__(self):
        return self.name




class ProjectRoomMember(TimeStampedModel):
    class Role(models.TextChoices):
        MANAGER = "manager", "Manager"
        CONTRIBUTOR = "contributor", "Contributor"
        VIEWER = "viewer", "Viewer"

    project_room = models.ForeignKey(ProjectRoom, on_delete=models.CASCADE, related_name="members")
    membership = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name="project_room_memberships")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CONTRIBUTOR)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="added_project_room_members")

    class Meta:
        constraints = [models.UniqueConstraint(fields=("project_room", "membership"), name="unique_project_room_member")]
        indexes = [models.Index(fields=["project_room", "role"], name="core_prmember_room_role_idx")]

class ProjectRoomPartner(TimeStampedModel):
    class AccessLevel(models.TextChoices):
        PARTNER = "partner", "Teaming Partner"
        SUBCONTRACTOR = "subcontractor", "Subcontractor"
        CONSULTANT = "consultant", "Consultant"
        VIEWER = "viewer", "Viewer"

    project_room = models.ForeignKey(ProjectRoom, on_delete=models.CASCADE, related_name="partners")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="shared_project_rooms")
    access_level = models.CharField(max_length=20, choices=AccessLevel.choices, default=AccessLevel.PARTNER)
    can_upload = models.BooleanField(default=True)
    can_comment = models.BooleanField(default=True)
    can_view_pricing = models.BooleanField(default=False)
    can_view_sensitive_documents = models.BooleanField(default=False)
    can_export = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="project_room_partner_invites")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("project_room", "organization"), name="unique_project_room_partner"),
        ]
        indexes = [
            models.Index(fields=["organization", "project_room"], name="core_projec_organiz_5d07a0_idx"),
            models.Index(fields=["project_room", "revoked_at", "expires_at"], name="core_prpartner_access_idx"),
        ]


class ProjectRoomTask(TimeStampedModel):
    class Status(models.TextChoices):
        TODO = "todo", "To Do"
        IN_PROGRESS = "in_progress", "In Progress"
        REVIEW = "review", "Review"
        DONE = "done", "Done"

    class Visibility(models.TextChoices):
        INTERNAL = "internal", "Owner Company Only"
        SHARED = "shared", "All Project Room Participants"

    project_room = models.ForeignKey(ProjectRoom, on_delete=models.CASCADE, related_name="collaboration_tasks")
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TODO)
    priority = models.CharField(max_length=20, default="medium")
    visibility = models.CharField(max_length=20, choices=Visibility.choices, default=Visibility.SHARED)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="project_room_tasks")
    due_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_project_room_tasks")
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["status", "sort_order", "due_date", "id"]
        indexes = [models.Index(fields=["project_room", "status", "visibility"], name="core_prtask_room_stat_vis_idx")]


class ProjectRoomComment(TimeStampedModel):
    class Visibility(models.TextChoices):
        INTERNAL = "internal", "Owner Company Only"
        SHARED = "shared", "All Project Room Participants"

    project_room = models.ForeignKey(ProjectRoom, on_delete=models.CASCADE, related_name="comments")
    task = models.ForeignKey(ProjectRoomTask, null=True, blank=True, on_delete=models.CASCADE, related_name="comments")
    body = models.TextField()
    visibility = models.CharField(max_length=20, choices=Visibility.choices, default=Visibility.SHARED)
    mentions = models.JSONField(default=list, blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="project_room_comments")

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["project_room", "visibility", "created_at"], name="core_prcomment_room_vis_idx")]


class ProjectRoomNote(TimeStampedModel):
    class Visibility(models.TextChoices):
        INTERNAL = "internal", "Owner Company Only"
        SHARED = "shared", "All Project Room Participants"

    project_room = models.ForeignKey(ProjectRoom, on_delete=models.CASCADE, related_name="notes")
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    visibility = models.CharField(max_length=20, choices=Visibility.choices, default=Visibility.INTERNAL)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="project_room_notes")

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["project_room", "visibility", "-updated_at"], name="core_prnote_room_vis_idx")]


class ProjectRoomFile(TimeStampedModel):
    class Visibility(models.TextChoices):
        INTERNAL = "internal", "Owner Company Only"
        SHARED = "shared", "All Project Room Participants"
        PRICING = "pricing", "Pricing Authorized Participants"
        SENSITIVE = "sensitive", "Sensitive Document Authorized Participants"

    project_room = models.ForeignKey(ProjectRoom, on_delete=models.CASCADE, related_name="collaboration_files")
    name = models.CharField(max_length=500)
    url = models.URLField(max_length=2000)
    description = models.TextField(blank=True)
    visibility = models.CharField(max_length=20, choices=Visibility.choices, default=Visibility.SHARED)
    version = models.PositiveIntegerField(default=1)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="project_room_files")

    class Meta:
        ordering = ["-updated_at"]
        constraints = [models.UniqueConstraint(fields=("project_room", "name", "version"), name="unique_project_room_file_version")]
        indexes = [models.Index(fields=["project_room", "visibility", "-updated_at"], name="core_prfile_room_vis_idx")]


class ProjectRoomActivity(TimeStampedModel):
    project_room = models.ForeignKey(ProjectRoom, on_delete=models.CASCADE, related_name="activity")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="project_room_activity")
    action = models.CharField(max_length=120)
    object_type = models.CharField(max_length=80, blank=True)
    object_id = models.CharField(max_length=80, blank=True)
    summary = models.CharField(max_length=500)
    visibility = models.CharField(max_length=20, choices=ProjectRoomNote.Visibility.choices, default=ProjectRoomNote.Visibility.SHARED)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["project_room", "visibility", "-created_at"], name="core_practivity_room_vis_idx")]


class CollaborationNotification(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="collaboration_notifications")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="forgegov_collaboration_notifications")
    project_room = models.ForeignKey(ProjectRoom, null=True, blank=True, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    kind = models.CharField(max_length=60, default="project_room")
    read = models.BooleanField(default=False)
    link = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "user", "read", "-created_at"], name="core_collabnotif_org_user_idx")]


class NotificationPreference(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="notification_preferences")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forgegov_notification_preferences")
    in_app_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=True)
    immediate_critical = models.BooleanField(default=True)
    daily_digest = models.BooleanField(default=True)
    weekly_digest = models.BooleanField(default=False)
    opportunity_alerts = models.BooleanField(default=True)
    opportunity_changes = models.BooleanField(default=True)
    deadlines = models.BooleanField(default=True)
    pipeline = models.BooleanField(default=True)
    project_room = models.BooleanField(default=True)
    security = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("organization", "user"), name="unique_notification_preference_per_workspace"),
        ]


class UserPreference(TimeStampedModel):
    class Theme(models.TextChoices):
        SYSTEM = "system", "System"
        LIGHT = "light", "Light"
        DARK = "dark", "Dark"

    class Density(models.TextChoices):
        COMFORTABLE = "comfortable", "Comfortable"
        COMPACT = "compact", "Compact"

    class AIResponseStyle(models.TextChoices):
        CONCISE = "concise", "Concise"
        BALANCED = "balanced", "Balanced"
        DETAILED = "detailed", "Detailed"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forgegov_preferences")
    theme = models.CharField(max_length=20, choices=Theme.choices, default=Theme.SYSTEM)
    density = models.CharField(max_length=20, choices=Density.choices, default=Density.COMFORTABLE)
    reduce_motion = models.BooleanField(default=False)
    sidebar_collapsed = models.BooleanField(default=False)
    ai_response_style = models.CharField(max_length=20, choices=AIResponseStyle.choices, default=AIResponseStyle.BALANCED)
    ai_live_web_enabled = models.BooleanField(default=True)
    ai_workspace_grounding_enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["user_id"]


class NotificationDelivery(TimeStampedModel):
    class Status(models.TextChoices):
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    organization = models.ForeignKey(Organization, null=True, blank=True, on_delete=models.SET_NULL, related_name="notification_deliveries")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="forgegov_notification_deliveries")
    channel = models.CharField(max_length=20, default="email")
    category = models.CharField(max_length=60, blank=True)
    recipient = models.EmailField(blank=True)
    subject = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SENT)
    error_message = models.CharField(max_length=1000, blank=True)
    related_object_type = models.CharField(max_length=80, blank=True)
    related_object_id = models.CharField(max_length=120, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status", "-created_at"], name="notif_delivery_org_status_idx"),
            models.Index(fields=["user", "-created_at"], name="notif_delivery_user_idx"),
        ]


class AIConversation(TimeStampedModel):
    class Visibility(models.TextChoices):
        INTERNAL = "internal", "Owner Company Only"
        SHARED = "shared", "Project Room Participants"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="ai_conversations")
    project_room = models.ForeignKey(ProjectRoom, null=True, blank=True, on_delete=models.CASCADE, related_name="ai_conversations")
    opportunity = models.ForeignKey(Opportunity, null=True, blank=True, on_delete=models.SET_NULL, related_name="ai_conversations")
    title = models.CharField(max_length=255, default="New conversation")
    visibility = models.CharField(max_length=20, choices=Visibility.choices, default=Visibility.INTERNAL)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="forgegov_ai_conversations")

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["organization", "-updated_at"], name="core_aicon_organiz_50f0c8_idx"), models.Index(fields=["project_room", "visibility"], name="core_aicon_project_26cf8b_idx")]


class AIMessage(TimeStampedModel):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        SYSTEM = "system", "System"

    conversation = models.ForeignKey(AIConversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    sources = models.JSONField(default=list, blank=True)
    model = models.CharField(max_length=120, blank=True)
    provider = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ["created_at"]

class OpportunityDocument(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="opportunity_documents")
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name="ingested_documents")
    project_room = models.ForeignKey(ProjectRoom, null=True, blank=True, on_delete=models.CASCADE, related_name="documents")
    file_name = models.CharField(max_length=500)
    source_url = models.URLField(max_length=2000)
    content_type = models.CharField(max_length=150, blank=True)
    checksum = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    page_count = models.PositiveIntegerField(default=0)
    character_count = models.PositiveIntegerField(default=0)
    error_message = models.CharField(max_length=1000, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["file_name"]
        constraints = [models.UniqueConstraint(fields=("organization", "opportunity", "source_url"), name="unique_ingested_opportunity_document")]
        indexes = [models.Index(fields=["organization", "opportunity", "status"], name="core_oppdoc_org_opp_status_idx")]

class OpportunityDocumentChunk(TimeStampedModel):
    document = models.ForeignKey(OpportunityDocument, on_delete=models.CASCADE, related_name="chunks")
    ordinal = models.PositiveIntegerField()
    page_number = models.PositiveIntegerField(null=True, blank=True)
    section = models.CharField(max_length=255, blank=True)
    text = models.TextField()

    class Meta:
        ordering = ["document_id", "ordinal"]
        constraints = [models.UniqueConstraint(fields=("document", "ordinal"), name="unique_opportunity_document_chunk")]
        indexes = [models.Index(fields=["document", "page_number", "ordinal"], name="core_oppchunk_doc_page_idx")]

class OpportunityAnalysis(TimeStampedModel):
    class AnalysisType(models.TextChoices):
        EXECUTIVE = "executive_summary", "Executive Summary"
        REQUIREMENTS = "requirements", "Requirements"
        RISKS = "risks", "Risk Assessment"
        BID_NO_BID = "bid_no_bid", "Bid / No-Bid"
        COMPLIANCE = "compliance_matrix", "Compliance Matrix"
        AMENDMENTS = "amendment_comparison", "Amendment Comparison"
        CAPTURE_COPILOT = "capture_copilot", "Capture Copilot"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="opportunity_analyses")
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name="analyses")
    project_room = models.ForeignKey(ProjectRoom, null=True, blank=True, on_delete=models.CASCADE, related_name="analyses")
    analysis_type = models.CharField(max_length=40, choices=AnalysisType.choices)
    content = models.TextField()
    sources = models.JSONField(default=list, blank=True)
    model = models.CharField(max_length=120, blank=True)
    input_fingerprint = models.CharField(max_length=64)
    contains_financial = models.BooleanField(default=False)
    uses_workspace_context = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_opportunity_analyses")

    class Meta:
        ordering = ["-updated_at"]
        constraints = [models.UniqueConstraint(fields=("organization", "opportunity", "project_room", "analysis_type", "input_fingerprint"), name="unique_cached_opportunity_analysis")]
        indexes = [models.Index(fields=["organization", "opportunity", "analysis_type"], name="core_oppanalysis_org_type_idx")]


class OrganizationProfile(TimeStampedModel):
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name="network_profile")
    tagline = models.CharField(max_length=240, blank=True)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    city = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=80, blank=True)
    country = models.CharField(max_length=80, blank=True, default="United States")
    naics_codes = models.JSONField(default=list, blank=True)
    psc_codes = models.JSONField(default=list, blank=True)
    capabilities = models.JSONField(default=list, blank=True)
    certifications = models.JSONField(default=list, blank=True)
    contract_vehicles = models.JSONField(default=list, blank=True)
    service_areas = models.JSONField(default=list, blank=True)
    contact_email = models.EmailField(blank=True)
    is_public = models.BooleanField(default=True)
    accepting_partners = models.BooleanField(default=True)
    verified = models.BooleanField(default=False)

    class Meta:
        ordering = ["organization__name"]


class NetworkConnection(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        BLOCKED = "blocked", "Blocked"
        CANCELLED = "cancelled", "Cancelled"
        DISCONNECTED = "disconnected", "Disconnected"

    requester = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="network_requests_sent")
    recipient = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="network_requests_received")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="network_connections_requested")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    message = models.TextField(blank=True)
    responded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="network_connections_responded")
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=("requester", "recipient"), name="unique_directional_network_connection"),
            models.CheckConstraint(condition=~models.Q(requester=models.F("recipient")), name="network_connection_distinct_orgs"),
        ]
        indexes = [
            models.Index(fields=["recipient", "status", "-created_at"], name="core_netconn_rec_stat_idx"),
            models.Index(fields=["requester", "status", "-created_at"], name="core_netconn_req_stat_idx"),
        ]




class OrganizationJoinRequest(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Cancelled"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="join_requests")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="organization_join_requests")
    email_domain = models.CharField(max_length=255)
    requested_role = models.CharField(max_length=20, choices=Membership.Role.choices, default=Membership.Role.VIEWER)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_organization_join_requests")
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=("organization", "user"), condition=models.Q(status="pending"), name="unique_pending_org_join_request")]

class ProjectRoomInvitation(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    project_room = models.ForeignKey(ProjectRoom, on_delete=models.CASCADE, related_name="partner_invitations")
    invited_organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="project_room_invitations")
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="project_room_invitations_sent")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    access_level = models.CharField(max_length=20, choices=ProjectRoomPartner.AccessLevel.choices, default=ProjectRoomPartner.AccessLevel.PARTNER)
    can_upload = models.BooleanField(default=True)
    can_comment = models.BooleanField(default=True)
    can_view_pricing = models.BooleanField(default=False)
    can_view_sensitive_documents = models.BooleanField(default=False)
    can_export = models.BooleanField(default=False)
    partner_expires_at = models.DateTimeField(null=True, blank=True)
    message = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    resend_count = models.PositiveSmallIntegerField(default=0)
    responded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="project_room_invitations_responded")
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=("project_room", "invited_organization"), condition=models.Q(status="pending"), name="unique_pending_project_room_invite")]
        indexes = [models.Index(fields=["invited_organization", "status", "-created_at"], name="core_prinvite_org_stat_idx")]


class BetaFeedback(TimeStampedModel):
    class Category(models.TextChoices):
        ISSUE = "issue", "Issue"
        SUGGESTION = "suggestion", "Suggestion"
        UX = "ux", "User Experience"
        DATA = "data", "Data / Connector"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        NEW = "new", "New"
        REVIEWING = "reviewing", "Reviewing"
        PLANNED = "planned", "Planned"
        FIXED = "fixed", "Fixed"
        CLOSED = "closed", "Closed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="forgegov_beta_feedback")
    organization = models.ForeignKey(Organization, null=True, blank=True, on_delete=models.SET_NULL, related_name="beta_feedback")
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.ISSUE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    page_path = models.CharField(max_length=500, blank=True)
    message = models.TextField()
    user_agent = models.TextField(blank=True)
    request_id = models.CharField(max_length=120, blank=True)
    admin_notes = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="forgegov_beta_feedback_resolved")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="beta_feedback_status_idx"),
            models.Index(fields=["organization", "-created_at"], name="beta_feedback_org_idx"),
        ]
