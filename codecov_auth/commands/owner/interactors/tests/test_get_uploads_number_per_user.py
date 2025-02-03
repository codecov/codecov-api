from datetime import datetime, timedelta

from django.test import TransactionTestCase
from shared.django_apps.codecov_auth.tests.factories import PlanFactory, TierFactory
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    OwnerFactory,
    RepositoryFactory,
)
from shared.django_apps.reports.models import ReportType
from shared.plan.constants import PlanName, TierName, TrialStatus
from shared.upload.utils import UploaderType, insert_coverage_measurement

from reports.tests.factories import CommitReportFactory, UploadFactory

from ..get_uploads_number_per_user import GetUploadsNumberPerUserInteractor


class GetUploadsNumberPerUserInteractorTest(TransactionTestCase):
    def setUp(self):
        self.tier = TierFactory(tier_name=TierName.BASIC.value)
        self.plan = PlanFactory(tier=self.tier, monthly_uploads_limit=250)
        self.user_with_no_uploads = OwnerFactory(plan=self.plan.name)
        self.user_with_uploads = OwnerFactory(plan=self.plan.name)
        repo = RepositoryFactory.create(author=self.user_with_uploads, private=True)
        commit = CommitFactory.create(repository=repo)
        report = CommitReportFactory.create(
            commit=commit, report_type=ReportType.COVERAGE.value
        )

        # Reports all created today/within the last 30 days
        for i in range(2):
            # Explicit add insert_coverage_measurement as we'll do this every time that we make an upload
            upload = UploadFactory.create(report=report)
            insert_coverage_measurement(
                owner_id=self.user_with_uploads.ownerid,
                repo_id=repo.repoid,
                commit_id=commit.id,
                upload_id=upload.id,
                uploader_used=UploaderType.CLI.value,
                private_repo=repo.private,
                report_type=report.report_type,
            )

        report_within_40_days = UploadFactory.create(report=report)
        report_within_40_days.created_at += timedelta(days=-40)
        report_within_40_days.save()

        # Trial Data
        trial_tier = TierFactory(tier_name=TierName.TRIAL.value)
        trial_plan = PlanFactory(
            tier=trial_tier,
            name=PlanName.TRIAL_PLAN_NAME.value,
            monthly_uploads_limit=250,
        )
        self.trial_owner = OwnerFactory(
            trial_status=TrialStatus.EXPIRED.value,
            trial_start_date=datetime.now() + timedelta(days=-10),
            trial_end_date=datetime.now() + timedelta(days=-2),
            plan=trial_plan.name,
        )
        trial_repo = RepositoryFactory.create(author=self.trial_owner, private=True)
        trial_commit = CommitFactory.create(repository=trial_repo)
        trial_report = CommitReportFactory.create(
            commit=trial_commit, report_type=ReportType.COVERAGE.value
        )

        report_before_trial = UploadFactory.create(report=trial_report)
        report_before_trial.created_at += timedelta(days=-12)
        report_before_trial.save()
        upload_before_trial = insert_coverage_measurement(
            owner_id=self.trial_owner.ownerid,
            repo_id=repo.repoid,
            commit_id=commit.id,
            upload_id=report_before_trial.id,
            uploader_used=UploaderType.CLI.value,
            private_repo=repo.private,
            report_type=report.report_type,
        )
        upload_before_trial.created_at += timedelta(days=-12)
        upload_before_trial.save()

        report_during_trial = UploadFactory.create(report=trial_report)
        report_during_trial.created_at += timedelta(days=-5)
        report_during_trial.save()
        upload_during_trial = insert_coverage_measurement(
            owner_id=self.trial_owner.ownerid,
            repo_id=repo.repoid,
            commit_id=commit.id,
            upload_id=report_during_trial.id,
            uploader_used=UploaderType.CLI.value,
            private_repo=repo.private,
            report_type=report.report_type,
        )
        upload_during_trial.created_at += timedelta(days=-5)
        upload_during_trial.save()

        report_after_trial = UploadFactory.create(report=trial_report)
        insert_coverage_measurement(
            owner_id=self.trial_owner.ownerid,
            repo_id=repo.repoid,
            commit_id=commit.id,
            upload_id=report_after_trial.id,
            uploader_used=UploaderType.CLI.value,
            private_repo=repo.private,
            report_type=report.report_type,
        )

    async def test_with_no_uploads(self):
        owner = self.user_with_no_uploads
        uploads = await GetUploadsNumberPerUserInteractor(None, owner).execute(owner)
        assert uploads == 0

    async def test_with_number_of_uploads(self):
        owner = self.user_with_uploads
        uploads = await GetUploadsNumberPerUserInteractor(None, owner).execute(owner)
        assert uploads == 2

    async def test_number_of_uploads_with_expired_trial(self):
        owner = self.trial_owner
        uploads = await GetUploadsNumberPerUserInteractor(None, owner).execute(owner)
        assert uploads == 2
