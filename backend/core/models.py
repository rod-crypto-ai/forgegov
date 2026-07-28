from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Organization(TimeStampedModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    uei = models.CharField(max_length=32, blank=True)
    cage_code = models.CharField(max_length=16, blank=True)

    def __str__(self):
        return self.name


class Membership(TimeStampedModel):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Administrator"
        CAPTURE = "capture", "Capture Manager"
        BD = "bd", "Business Development"
        PROPOSAL = "proposal", "Proposal Writer"
        VIEWER = "viewer", "Read Only"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="organization_memberships")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.VIEWER)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("organization", "user"), name="unique_organization_membership"),
        ]


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
        REVOKED = "revoked", "Revoked"
        EXPIRED = "expired", "Expired"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=Membership.Role.choices, default=Membership.Role.VIEWER)
    token = models.CharField(max_length=128, unique=True)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="sent_forgegov_invitations")
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

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
    read = models.BooleanField(default=False)
    dismissed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "saved_search", "source_id", "alert_type"),
                name="unique_saved_search_intelligence_alert",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "read", "-created_at"], name="core_intell_organiz_3309e7_idx"),
            models.Index(fields=["source_id"], name="core_intell_source__cba733_idx"),
        ]

    def __str__(self):
        return self.title
