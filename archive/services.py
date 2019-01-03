from django.conf import settings
from minio import Minio
from hashlib import md5
from base64 import b16encode


def get_repository_archive_hash(repository):
    repo_id, service, service_id = repository.repo_id, repository.service, repository.service_id
    assert repo_id and service_id, (500, 'Missing information to build aws key.')
    _hash = md5()
    _hash.update(''.join((repo_id,
                          service,
                          service_id,
                          settings.MINIO_HASH_KEY or '')))
    return b16encode(_hash.digest())


def get_minio_client():
    return Minio(
        settings.MINIO_LOCATION,
        access_key=settings.MINIO_SECRET_KEY,
        secret_key=settings.MINIO_ACCESS_KEY,
        secure=True
    )


def get_commit_archive_path(commit):
    return commit.minio_report_path


def get_session_report(session):
    path = session['a']
    minio_client = get_minio_client()
    return minio_client.get_object(settings.ARCHIVE_BUCKET_NAME, path)
