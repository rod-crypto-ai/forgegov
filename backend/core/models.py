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
    job_title = models.CharField(max_length=120, blank=True)
    department = models.CharField(max_length=120, blank=True)
    active = models.BooleanField(default=True)

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
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="project_room_partner_invites")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("project_room", "organization"), name="unique_project_room_partner"),
        ]
        indexes = [models.Index(fields=["organization", "project_room"], name="core_projec_organiz_5d07a0_idx")]


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

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="opportunity_analyses")
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name="analyses")
    project_room = models.ForeignKey(ProjectRoom, null=True, blank=True, on_delete=models.CASCADE, related_name="analyses")
    analysis_type = models.CharField(max_length=40, choices=AnalysisType.choices)
    content = models.TextField()
    sources = models.JSONField(default=list, blank=True)
    model = models.CharField(max_length=120, blank=True)
    input_fingerprint = models.CharField(max_length=64)
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
