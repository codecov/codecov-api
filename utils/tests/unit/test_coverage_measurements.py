from datetime import datetime, timedelta
from unittest.mock import PropertyMock, patch

from django.test import TestCase
from freezegun import freeze_time

from codecov_auth.models import Owner
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory
from plan.service import PlanService
from reports.tests.factories import CommitReportFactory, UploadFactory
from user_measurements.models import UserMeasurement
from utils.uploads_used import (
    insert_coverage_measurement,
    query_monthly_coverage_measurements,
)


class CoverageMeasurement(TestCase):
    def add_upload_measurements_records(
        self,
        owner: Owner,
        quantity: int,
        report_type="coverage",
        private=True,
    ):
        for _ in range(quantity):
            repo = RepositoryFactory.create(author=owner, private=private)
            commit = CommitFactory.create(repository=repo)
            report = CommitReportFactory.create(commit=commit, report_type=report_type)
            upload = UploadFactory.create(report=report)
            insert_coverage_measurement(
                owner=owner,
                repo=repo,
                commit=commit,
                upload=upload,
                uploader_used="CLI",
                private_repo=repo.private,
                report_type=report.report_type,
            )

    def test_query_monthly_coverage_measurements(self):
        owner = OwnerFactory()
        self.add_upload_measurements_records(owner=owner, quantity=5)
        plan_service = PlanService(current_org=owner)

        monthly_measurements = query_monthly_coverage_measurements(
            plan_service=plan_service
        )
        assert monthly_measurements == 5

    def test_query_monthly_coverage_measurements_with_a_public_repo(self):
        owner = OwnerFactory()
        self.add_upload_measurements_records(owner=owner, quantity=3)
        self.add_upload_measurements_records(owner=owner, quantity=1, private=False)

        plan_service = PlanService(current_org=owner)
        monthly_measurements = query_monthly_coverage_measurements(
            plan_service=plan_service
        )
        # Doesn't query the last 3
        assert monthly_measurements == 3

    def test_query_monthly_coverage_measurements_with_non_coverage_report(self):
        owner = OwnerFactory()
        self.add_upload_measurements_records(owner=owner, quantity=3)
        self.add_upload_measurements_records(
            owner=owner, quantity=1, report_type="bundle_analysis"
        )

        plan_service = PlanService(current_org=owner)
        monthly_measurements = query_monthly_coverage_measurements(
            plan_service=plan_service
        )
        # Doesn't query the last 3
        assert monthly_measurements == 3

    def test_query_monthly_coverage_measurements_after_30_days(self):
        owner = OwnerFactory()

        # Uploads before 30 days
        freezer = freeze_time("2023-10-15T00:00:00")
        freezer.start()
        self.add_upload_measurements_records(owner=owner, quantity=3)
        freezer.stop()

        # Uploads within the last 30 days
        freezer = freeze_time("2024-02-10T00:00:00")
        freezer.start()
        self.add_upload_measurements_records(owner=owner, quantity=5)
        freezer.stop()

        all_measurements = UserMeasurement.objects.all()
        assert len(all_measurements) == 8

        plan_service = PlanService(current_org=owner)
        # Now
        freezer = freeze_time("2024-03-05T00:00:00")
        freezer.start()
        monthly_measurements = query_monthly_coverage_measurements(
            plan_service=plan_service
        )
        freezer.stop()
        assert monthly_measurements == 5

    def test_query_monthly_coverage_measurements_excluding_uploads_during_trial(self):
        freezer = freeze_time("2024-02-01T00:00:00")
        freezer.start()
        owner = OwnerFactory(
            trial_status="expired",
            trial_start_date=datetime.utcnow(),
            trial_end_date=datetime.utcnow() + timedelta(days=14),
        )
        freezer.stop()

        freezer = freeze_time("2024-02-05T00:00:00")
        freezer.start()
        self.add_upload_measurements_records(owner=owner, quantity=3)
        freezer.stop()

        # Now
        freezer = freeze_time("2024-02-20T00:00:00")
        freezer.start()
        self.add_upload_measurements_records(owner=owner, quantity=6)

        all_measurements = UserMeasurement.objects.all()
        assert len(all_measurements) == 9

        plan_service = PlanService(current_org=owner)
        monthly_measurements = query_monthly_coverage_measurements(
            plan_service=plan_service
        )
        freezer.stop()
        assert monthly_measurements == 6

    @patch("plan.service.PlanService.monthly_uploads_limit", new_callable=PropertyMock)
    def test_query_monthly_coverage_measurements_beyond_monthly_limit(
        self, monthly_uploads_mock
    ):
        owner = OwnerFactory()
        self.add_upload_measurements_records(owner=owner, quantity=10)

        plan_service = PlanService(current_org=owner)
        monthly_uploads_mock.return_value = 3
        monthly_measurements = query_monthly_coverage_measurements(
            plan_service=plan_service
        )
        # 10 uploads total, max 3 returned
        assert monthly_measurements == 3
