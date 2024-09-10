import logging
from base64 import b16encode
from enum import Enum
from hashlib import md5
from uuid import uuid4

from django.utils import timezone

from services.storage import StorageService
from utils.config import get_config

log = logging.getLogger(__name__)


class MinioEndpoints(Enum):
    chunks = "{version}/repos/{repo_hash}/commits/{commitid}/chunks.txt"

    raw_with_upload_id = (
        "v4/raw/{date}/{repo_hash}/{commit_sha}/{reportid}/{uploadid}.txt"
    )
    profiling_upload = (
        "{version}/repos/{repo_hash}/profilinguploads/{profiling_version}/{location}"
    )
    static_analysis_single_file = (
        "{version}/repos/{repo_hash}/static_analysis/files/{location}"
    )
    test_results = "test_results/v1/raw/{date}/{repo_hash}/{commit_sha}/{uploadid}.txt"

    def get_path(self, **kwaargs):
        return self.value.format(**kwaargs)


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
    Time to life, how long presigned PUTs/GETs should live
    """
    ttl = 10

    def __init__(self, repository, ttl=None):
        self.root = get_config("services", "minio", "bucket", default="archive")
        self.region = get_config("services", "minio", "region", default="us-east-1")
        # Set TTL from config and default to existing value
        self.ttl = ttl or int(get_config("services", "minio", "ttl", default=self.ttl))
        self.storage = StorageService()
        self.storage_hash = self.get_archive_hash(repository)

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

    def read_file(self, path):
        """
        Generic method to read a file from the archive
        """
        contents = self.storage.read_file(self.root, path)
        return contents.decode()

    def read_chunks(self, commit_sha):
        """
        Convenience method to read a chunks file from the archive.
        """
        path = MinioEndpoints.chunks.get_path(
            version="v4", repo_hash=self.storage_hash, commitid=commit_sha
        )
        log.info("Downloading chunks from path %s for commit %s", path, commit_sha)
        return self.read_file(path)

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
