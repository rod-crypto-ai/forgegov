from django.core.management.base import BaseCommand, CommandError

from core.intelligence.services.award_ingestion import sync_usaspending_awards


class Command(BaseCommand):
    help = "Incrementally ingest normalized federal awards from USAspending."

    def add_arguments(self, parser):
        parser.add_argument("--start-date")
        parser.add_argument("--end-date")
        parser.add_argument("--pages", type=int, default=1)
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--keyword", default="")
        parser.add_argument("--agency", default="")
        parser.add_argument("--naics", default="")

    def handle(self, *args, **options):
        run = sync_usaspending_awards(
            start_date=options.get("start_date"),
            end_date=options.get("end_date"),
            pages=options["pages"],
            limit=options["limit"],
            keyword=options["keyword"],
            agency=options["agency"],
            naics=options["naics"],
        )
        self.stdout.write(self.style.SUCCESS(
            f"status={run.status} seen={run.records_seen} created={run.records_created} updated={run.records_updated} errors={len(run.errors)}"
        ))
        if run.status == run.Status.FAILED:
            raise CommandError("USAspending award sync failed. See AwardSyncRun.errors.")
