from django.db import models
from shared.staticanalysis import StaticAnalysisSingleFileSnapshotState

from codecov.models import BaseCodecovModel


class StaticAnalysisSuite(BaseCodecovModel):
    commit = models.ForeignKey("core.Commit", on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["external_id"], name="staticanalysis_external_id_uniq"
            ),
        ]


class StaticAnalysisSingleFileSnapshot(BaseCodecovModel):
    repository = models.ForeignKey("core.Repository", on_delete=models.CASCADE)
    file_hash = models.UUIDField(null=False)
    content_location = models.TextField()
    state_id = models.IntegerField(
        choices=StaticAnalysisSingleFileSnapshotState.choices()
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["repository", "file_hash"], name="staticanalysis_repo_filehash"
            ),
        ]


class StaticAnalysisSuiteFilepath(BaseCodecovModel):
    analysis_suite = models.ForeignKey(
        StaticAnalysisSuite, on_delete=models.CASCADE, related_name="filepaths"
    )
    file_snapshot = models.ForeignKey(
        StaticAnalysisSingleFileSnapshot,
        on_delete=models.CASCADE,
        related_name="filepaths",
    )
    filepath = models.TextField()

    @property
    def file_hash(self):
        # TODO: double check so serializer doesnt get N + 1 queries
        return self.file_snapshot.file_hash
