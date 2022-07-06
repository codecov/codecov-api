import logging

import dateutil.parser as dateparser
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from codecov_auth.models import Owner
from core.models import Repository
from timeseries.helpers import refresh_measurement_summaries, save_repo_measurements

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Backfills timeseries measurement data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--start-date", type=str, required=True, help="i.e. YYYY-MM-DD"
        )
        parser.add_argument(
            "--end-date", type=str, required=False, help="i.e. YYYY-MM-DD"
        )
        parser.add_argument("--owner", type=str, required=True, help="owner username")
        parser.add_argument("--repo", type=str, required=False, help="repository name")
        parser.add_argument(
            "--service",
            type=str,
            default="github",
            help="Git service provider",
        )
        parser.add_argument(
            "--refresh",
            action="store_true",
            help="refresh aggregate summaries",
        )

    def handle(self, *args, **options):
        if not settings.TIMESERIES_ENABLED:
            raise CommandError(f"Timeseries not enabled")

        start_date = dateparser.isoparse(options["start_date"]).replace(
            tzinfo=timezone.get_current_timezone()
        )
        if options["end_date"] is not None:
            end_date = dateparser.isoparse(options["end_date"]).replace(
                tzinfo=timezone.get_current_timezone()
            )
        else:
            end_date = timezone.now()

        owner_name = options["owner"]
        service = options["service"]
        owner = Owner.objects.filter(username=owner_name, service=service).first()
        if owner is None:
            raise CommandError(f"No such owner: {owner_name}")

        repo_name = options["repo"]
        if repo_name is not None:
            repo = Repository.objects.filter(author=owner, name=repo_name).first()
            if repo is None:
                raise CommandError(f"No such repo: {owner_name}/{repo_name}")

            logger.info(f"saving measurements for repo: {owner_name}/{repo_name}")
            save_repo_measurements(repo, start_date=start_date, end_date=end_date)
        else:
            repos = Repository.objects.filter(author=owner, deleted=False)
            for repo in repos.iterator():
                logger.info(f"saving measurements for repo: {owner_name}/{repo.name}")
                save_repo_measurements(repo, start_date=start_date, end_date=end_date)

        if options["refresh"]:
            logger.info(
                f"refreshing measurement summaries from {start_date} to {end_date}"
            )
            refresh_measurement_summaries(start_date, end_date)
