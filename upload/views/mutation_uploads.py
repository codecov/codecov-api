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
from upload.views.uploads import UploadViews

log = logging.getLogger(__name__)


# TODO: Eventually this will be changed for a Mixin or something like that,
# I'm dpoing this just to avoid re-writing things
# This class inherits from the common Upload views to re-use helper functions get_repo, get_commit and get_report
class MutationTestUploadView(UploadViews):
    serializer_class = MutationTestUploadSerializer
    permission_classes = [
        # TODO: Add correct permissions
        AllowAny,
    ]
    # TODO: add throttle classes
    # TODO: add authentication classes

    def perform_create(self, serializer: MutationTestUploadSerializer):
        repository = self.get_repo()
        commit = self.get_commit(repository)
        report = self.get_report(commit)

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
        instance = serializer.save(storage_path=path, report_id=report.id)

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
