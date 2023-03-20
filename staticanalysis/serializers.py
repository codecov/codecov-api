import logging

from rest_framework import exceptions, serializers

from core.models import Commit
from services.archive import ArchiveService, MinioEndpoints
from staticanalysis.models import (
    StaticAnalysisSingleFileSnapshot,
    StaticAnalysisSingleFileSnapshotState,
    StaticAnalysisSuite,
    StaticAnalysisSuiteFilepath,
)

log = logging.getLogger(__name__)


class CommitFromShaSerializerField(serializers.Field):
    def to_representation(self, commit):
        return commit.commitid

    def to_internal_value(self, commit_sha):
        # TODO: Change this query when we change how we fetch URLs
        commit = Commit.objects.filter(
            repository__in=self.context["request"].auth.get_repositories(),
            commitid=commit_sha,
        ).first()
        if commit is None:
            raise exceptions.NotFound()
        return commit


def _dict_to_suite_filepath(
    analysis_suite,
    repository,
    archive_service,
    existing_file_snapshots_mapping,
    file_dict,
):
    if file_dict["file_hash"] in existing_file_snapshots_mapping:
        db_element = existing_file_snapshots_mapping[file_dict["file_hash"]]
        was_created = False
    else:
        path = MinioEndpoints.static_analysis_single_file.get_path(
            version="v4",
            repo_hash=archive_service.storage_hash,
            location=f"{file_dict['file_hash']}.json",
        )
        # Using get or create in the case the object was already
        # created somewhere else first, but also because get_or_create
        # is internally get_or_create_or_get, so Django handles the conflicts
        # that can arise on race conditions on the create step
        # We might choose to change it if the number of extra GETs become too much
        (
            db_element,
            was_created,
        ) = StaticAnalysisSingleFileSnapshot.objects.get_or_create(
            file_hash=file_dict["file_hash"],
            repository=repository,
            defaults=dict(
                state_id=StaticAnalysisSingleFileSnapshotState.CREATED.db_id,
                content_location=path,
            ),
        )
    if was_created:
        log.debug(
            "Created new snapshot for repository",
            extra=dict(repoid=repository.repoid, snapshot_id=db_element.id),
        )
    return StaticAnalysisSuiteFilepath(
        filepath=file_dict["filepath"],
        file_snapshot=db_element,
        analysis_suite=analysis_suite,
    )


class StaticAnalysisSuiteFilepathField(serializers.ModelSerializer):
    file_hash = serializers.UUIDField()
    raw_upload_location = serializers.SerializerMethodField()
    state = serializers.SerializerMethodField()

    class Meta:
        model = StaticAnalysisSuiteFilepath
        fields = [
            "filepath",
            "file_hash",
            "raw_upload_location",
            "state",
        ]

    def get_state(self, obj):
        return StaticAnalysisSingleFileSnapshotState.enum_from_int(
            obj.file_snapshot.state_id
        ).name

    def get_raw_upload_location(self, obj):
        # TODO: This has a built-in ttl of 10 seconds.
        # We have to consider changing it in case customers are doing a few
        # thousand uploads on the first time
        return self.context["archive_service"].create_presigned_put(
            obj.file_snapshot.content_location
        )


class FilepathListField(serializers.ListField):
    child = StaticAnalysisSuiteFilepathField()

    def to_representation(self, data):
        data = data.select_related(
            "file_snapshot",
        ).all()
        repo = data.first().file_snapshot.repository
        self.context["archive_service"] = ArchiveService(repo, ttl=60)
        return super().to_representation(data)


class StaticAnalysisSuiteSerializer(serializers.ModelSerializer):
    commit = CommitFromShaSerializerField(required=True)
    filepaths = FilepathListField()

    class Meta:
        model = StaticAnalysisSuite
        fields = ["external_id", "commit", "filepaths"]
        read_only_fields = ["raw_upload_location", "external_id"]

    def create(self, validated_data):
        file_metadata_array = validated_data.pop("filepaths")
        # `validated_data` only contains `commit` after pop
        obj = StaticAnalysisSuite.objects.create(**validated_data)
        request = self.context["request"]
        repository = request.auth.get_repositories()[0]
        archive_service = ArchiveService(repository)
        all_hashes = [val["file_hash"] for val in file_metadata_array]
        existing_values = StaticAnalysisSingleFileSnapshot.objects.filter(
            repository=repository, file_hash__in=all_hashes
        )
        existing_values_mapping = {val.file_hash: val for val in existing_values}
        created_filepaths = [
            _dict_to_suite_filepath(
                obj,
                repository,
                archive_service,
                existing_values_mapping,
                file_dict,
            )
            for file_dict in file_metadata_array
        ]
        StaticAnalysisSuiteFilepath.objects.bulk_create(created_filepaths)
        log.info(
            "Created static analysis filepaths",
            extra=dict(
                created_ids=[f.id for f in created_filepaths], repoid=repository.repoid
            ),
        )
        return obj
