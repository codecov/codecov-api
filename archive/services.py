from django.conf import settings
from minio import Minio
import requests
from covreports.resources import Report


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


def download_content(url):
    return requests.get(url).content


class ArchiveService(object):

    def build_report_from_commit(self, commit):
        repo_hash = commit.repo_hash
        commitid = commit.commitid
        url = f'{settings.MINIO_LOCATION}/v4/repos/{repo_hash}/commits/{commitid}/chunks.txt'
        chunks = download_content(url)
        files = commit.report['files']
        sessions = commit.report['sessions']
        totals = commit.totals
        return build_report(chunks, files, sessions, totals)
