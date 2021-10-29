import logging
from base64 import b16encode
from enum import Enum
from hashlib import md5
from uuid import uuid4

from django.conf import settings
from django.utils import timezone
from minio import Minio
from shared.helpers.flag import Flag
from shared.reports.resources import Report

from services.storage import StorageService
from utils.config import get_config

log = logging.getLogger(__name__)


class MinioEndpoints(Enum):
    chunks = "{version}/repos/{repo_hash}/commits/{commitid}/chunks.txt"
    raw = "v4/raw/{date}/{repo_hash}/{commit_sha}/{reportid}.txt"
    profiling_upload = (
        "{version}/repos/{repo_hash}/profilinguploads/{profiling_version}/{location}"
    )

    def get_path(self, **kwaargs):
        return self.value.format(**kwaargs)


class SerializableReport(Report):
    def file_reports(self):
        for f in self.files:
            yield self.get(f)

    @property
    def flags(self):
        """returns dict(:name=<Flag>)
        """
        flags_dict = {}
        for sid, session in self.sessions.items():
            if session.flags is not None:
                for flag in session.flags:
                    flags_dict[flag] = Flag(self, flag)
        return flags_dict


def get_minio_client():
    return Minio(
        settings.MINIO_LOCATION,
        access_key=settings.MINIO_SECRET_KEY,
        secret_key=settings.MINIO_ACCESS_KEY,
        secure=True,
    )


def build_report(chunks, files, sessions, totals):
    return SerializableReport(
        chunks=chunks, files=files, sessions=sessions, totals=totals
    )


# Service class for performing archive operations. Meant to work against the
# underlying StorageService
class ArchiveService(object):

    """
    The root level of the archive. In s3 terms,
    this would be the name of the bucket
    """

    root = None

    """
    Region where the storage is located.
    """
    region = None

    """
    A hash key of the repo for internal storage
    """
    storage_hash = None

    """
    Boolean. True if enterprise, False if not.
    """
    enterprise = False

    """
    Time to life, how long presigned PUTs/GETs should live
    """
    ttl = 10

    def __init__(self, repository):
        self.root = get_config("services", "minio", "bucket", default="archive")
        self.region = get_config("services", "minio", "region", default="us-east-1")
        self.enterprise = bool(get_config("setup", "enterprise_license"))

        self.storage = StorageService()
        self.storage_hash = self.get_archive_hash(repository)

    """
    Accessor for underlying StorageService. You typically shouldn't need
    this for anything.
    """

    def storage_client(self):
        return self.storage

    """
    Getter. Returns true if the current configuration is enterprise.
    """

    def is_enterprise(self):
        return self.enterprise

    """
    Generates a hash key from repo specific information.
    Provides slight obfuscation of data in minio storage
    """

    @classmethod
    def get_archive_hash(cls, repository):
        _hash = md5()
        hash_key = get_config("services", "minio", "hash_key", default="")
        val = "".join(
            map(
                str,
                (
                    repository.repoid,
                    repository.service,
                    repository.service_id,
                    hash_key,
                ),
            )
        ).encode()
        _hash.update(val)
        return b16encode(_hash.digest()).decode()

    """
    Grabs path from storage, adds data to path object
    writes back to path, overwriting the original contents
    """

    def update_archive(self, path, data):
        self.storage.append_to_file(self.root, path, data)

    """
    Writes a generic file to the archive -- it's typically recommended to
    not use this in lieu of the convenience methods write_raw_upload and
    write_chunks
    """

    def write_file(self, path, data, reduced_redundancy=False, gzipped=False):
        self.storage.write_file(
            self.root,
            path,
            data,
            reduced_redundancy=reduced_redundancy,
            gzipped=gzipped,
        )

    """
    Convenience write method, writes a raw upload to a destination.
    Returns the path it writes.
    """

    def write_raw_upload(self, commit_sha, report_id, data, gzipped=False):
        # create a custom report path for a raw upload.
        # write the file.
        path = "/".join(
            (
                "v4/raw",
                timezone.now().strftime("%Y-%m-%d"),
                self.storage_hash,
                commit_sha,
                "%s.txt" % report_id,
            )
        )

        self.write_file(path, data, gzipped=gzipped)

        return path

    """
    Convenience method to write a chunks.txt file to storage.
    """

    def write_chunks(self, commit_sha, data):
        path = MinioEndpoints.chunks.get_path(
            version="v4", repo_hash=self.storage_hash, commitid=commit_sha
        )

        self.write_file(path, data)
        return path

    """
    Generic method to read a file from the archive
    """

    def read_file(self, path):
        contents = self.storage.read_file(self.root, path)
        return contents.decode()

    """
    Generic method to delete a file from the archive.
    """

    def delete_file(self, path):
        self.storage.delete_file(self.root, path)

    """
    Deletes an entire repository's contents
    """

    def delete_repo_files(self):
        path = "v4/repos/{}".format(self.storage_hash)
        objects = self.storage.list_folder_contents(self.root, path)
        for obj in objects:
            self.storage.delete_file(self.root, obj.object_name)

    """
    Convenience method to read a chunks file from the archive.
    """

    def read_chunks(self, commit_sha):
        path = MinioEndpoints.chunks.get_path(
            version="v4", repo_hash=self.storage_hash, commitid=commit_sha
        )
        log.info("Downloading chunks from path %s for commit %s", path, commit_sha)
        return self.read_file(path)

    """
    Delete a chunk file from the archive
    """

    def delete_chunk_from_archive(self, commit_sha):
        path = "v4/repos/{}/commits/{}/chunks.txt".format(self.storage_hash, commit_sha)

        self.delete_file(path)

    def create_presigned_put(self, path):
        return self.storage.create_presigned_put(self.root, path, self.ttl)

    def create_raw_upload_presigned_put(
        self, commit_sha, repo_hash=None, filename=None, expires=None
    ):
        if repo_hash is None:
            repo_hash = self.storage_hash

        if not filename:
            filename = "{}.txt".format(uuid4())

        path = "v4/raw/{}/{}/{}/{}".format(
            timezone.now().strftime("%Y-%m-%d"), self.storage_hash, commit_sha, filename
        )

        if expires is None:
            expires = self.ttl

        return self.storage.create_presigned_put(self.root, path, expires)


class ReportService(object):
    """
    Class that centralizes all the high-level archive-related logic.

    Examples of responsabilities it has:
        - Fetch a report for a specific commit
    """

    def build_report_from_commit(self, commit):
        """Builds a `shared.reports.resources.Report` from a given commit

        Args:
            commit (core.models.Commit): The commit we want to see the report about

        Returns:
            SerializableReport: A report with all information from such commit
        """
        if not commit.report:
            return None
        commitid = commit.commitid
        chunks = ArchiveService(commit.repository).read_chunks(commitid)
        files = commit.report["files"]
        sessions = commit.report["sessions"]
        totals = commit.totals
        return build_report(chunks, files, sessions, totals)
