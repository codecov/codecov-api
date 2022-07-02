import logging
import re
from uuid import uuid4

from django.core.exceptions import PermissionDenied
from django.utils import timezone
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import AllowAny
from shared.metrics import metrics

from core.models import Commit, Repository
from services.archive import ArchiveService, MinioEndpoints
from services.task import TaskService
from upload.serializers import MutationTestUploadSerializer
from upload.throttles import UploadsPerCommitThrottle, UploadsPerWindowThrottle

log = logging.getLogger(__name__)


class MutationTestUploadView(ListCreateAPIView):
    serializer_class = MutationTestUploadSerializer
    permission_classes = [
        AllowAny,
    ]
    throttle_classes = [UploadsPerCommitThrottle, UploadsPerWindowThrottle]
    # TODO: add authentication class

    def perform_create(self, serializer: MutationTestUploadSerializer):
        repoid = self.kwargs["repo"]
        commitid = self.kwargs["commitid"]
        commit: Commit = Commit.objects.get(commitid=commitid)
        repository: Repository = Repository.objects.get(name=repoid)

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
