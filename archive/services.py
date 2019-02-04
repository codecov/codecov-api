from django.conf import settings
from enum import Enum
from minio import Minio
from covreports.resources import Report


class MinioEndpoints(Enum):
    chunks = '/{version}/repos/{repo_hash}/commits/{commitid}/chunks.txt'

    def get_path(self, **kwaargs):
        return self.value.format(**kwaargs)


class SerializableReport(Report):

    def file_reports(self):
        for f in self.files:
            yield self.get(f)


def get_minio_client():
    return Minio(
        settings.MINIO_LOCATION,
        access_key=settings.MINIO_SECRET_KEY,
        secret_key=settings.MINIO_ACCESS_KEY,
        secure=True
    )


def build_report(chunks, files, sessions, totals):
    return SerializableReport(chunks=chunks, files=files, sessions=sessions, totals=totals)


def download_content(minio_endpoint, **kwargs):
    """Downloads the content from minio service on endpoint `minio_endpoint`

    Args:
        minio_endpoint (MinioEndpoints): The endpoint we want to use
        **kwargs : The params of the above endpoint (filled with .format method)

    Returns:
        The content of the specific key on Minio
        str
    """
    path = minio_endpoint.get_path(**kwargs)
    return get_minio_client().get_object(path)


class ArchiveService(object):
    """
    Class that centralizes all the high-level archive-related logic.

    Examples of responsabilities it has:
        - Fetch a report for a specific commit
    """

    def build_report_from_commit(self, commit):
        """Builds a `covreports.resources.Report` from a given commit

        Args:
            commit (core.models.Commit): The commit we want to see the report about

        Returns:
            SerializableReport: A report with all information from such commit
        """
        repo_hash = commit.repo_hash
        commitid = commit.commitid
        chunks = download_content(
            MinioEndpoints.chunks, version='v4', repo_hash=repo_hash, commitid=commitid
        )
        files = commit.report['files']
        sessions = commit.report['sessions']
        totals = commit.totals
        return build_report(chunks, files, sessions, totals)
