import logging

from django.core.exceptions import PermissionDenied
from django.forms import ValidationError
from django.utils import timezone
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import AllowAny

from core.models import Commit, Repository
from reports.models import CommitReport
from services.archive import ArchiveService, MinioEndpoints
from services.task import TaskService
from upload.serializers import MutationTestUploadSerializer

log = logging.getLogger(__name__)


class MutationTestUploadView(ListCreateAPIView):
    serializer_class = MutationTestUploadSerializer
    permission_classes = [
        # TODO: Add correct permissions
        AllowAny,
    ]
    # TODO: add throttle classes
    # TODO: add authentication classes

    def perform_create(self, serializer: MutationTestUploadSerializer):
        commit: Commit = self.get_commit()
        repository: Repository = self.get_repo()

        # TEMP - Only codecov repos can uplaod mutation testing reports for now
        # REVIEW: check how to make this verification
        if not (
            repository.author.name.lower() == "codecov"
            or repository.author.username.lower() == "codecov"
        ):
            raise PermissionDenied("Feature not currently available")

        archive_service = ArchiveService(repository)
        path = MinioEndpoints.mutation_testing_upload.get_path(
            version="v0",
            date=timezone.now().strftime("%Y-%m-%d"),
            repo_hash=archive_service.storage_hash,
            commit_sha=commit.commitid,
            reportid=serializer.validated_data["name"],
        )
        upload_url = archive_service.create_presigned_put(path)
        instance = serializer.save(storage_path=path, report_id=self.kwargs["reportid"])

        log.info(
            "Dispatching mutation test upload to worker (mutation testing upload)",
            extra=dict(
                repoid=repository.repoid,
                commitid=commit.commitid,
                upload_path=upload_url,
            ),
        )
        # Send task to worker
        TaskService().mutation_test_upload(
            repoid=repository.repoid, commitid=commit.commitid, upload_path=upload_url
        )
        return instance

    def get_repo(self) -> Repository:
        # TODO this is not final - how is getting the repo is still in discuss
        repoid = self.kwargs["repo"]
        try:
            repository = Repository.objects.get(name=repoid)
            return repository
        except Repository.DoesNotExist:
            raise ValidationError(f"Repository {repoid} not found")

    def get_commit(self) -> Commit:
        commit_sha = self.kwargs["commit_sha"]
        repository = self.get_repo()
        try:
            commit = Commit.objects.get(
                commitid=commit_sha, repository__repoid=repository.repoid
            )
            return commit
        except Commit.DoesNotExist:
            raise ValidationError(f"Commit {commit_sha} not found")

    def get_report(self) -> CommitReport:
        report_id = self.kwargs["reportid"]
        commit = self.get_commit()
        try:
            report = CommitReport.objects.get(
                external_id__exact=report_id, commit__commitid=commit.commitid
            )
            return report
        except CommitReport.DoesNotExist:
            raise ValidationError(f"Report {report_id} not found")
