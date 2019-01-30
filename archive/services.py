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


def download_content(path):
    return get_minio_client().get_object(path)


class ArchiveService(object):

    def build_report_from_commit(self, commit):
        repo_hash = commit.repo_hash
        commitid = commit.commitid
        url = MinioEndpoints.chunks.get_path(version='v4', repo_hash=repo_hash, commitid=commitid)
        chunks = download_content(url)
        files = commit.report['files']
        sessions = commit.report['sessions']
        totals = commit.totals
        return build_report(chunks, files, sessions, totals)
