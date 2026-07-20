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
