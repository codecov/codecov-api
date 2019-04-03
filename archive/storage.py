import logging

import os
import sys
import gzip
import minio
from minio.error import (ResponseError, BucketAlreadyOwnedByYou,
                         BucketAlreadyExists)
from io import BytesIO

from utils.config import get_config

log = logging.getLogger(__name__)


# Service class for interfacing with codecov's underlying storage layer, minio
class   StorageService(object):

    def __init__(self, in_config=None):
        # init minio
        if in_config is None:
            self.minio_config = get_config('services', 'minio', default={})
        else:
            self.minio_config = in_config

        self.minio_client = self.init_minio_client(
            os.getenv('MINIO_PORT_9000_TCP_ADDR', '172.17.0.2'),
            os.getenv('MINIO_PORT_9000_TCP_PORT', '9000'),
            self.minio_config['access_key_id'],
            self.minio_config['secret_access_key'],
            self.minio_config['verify_ssl']
        )

    def client(self):
        return self.minio_client if self.minio_client else None

    def init_minio_client(self, host, port, access_key, secret_key, verify_ssl):
        return minio.Minio(
            '{}:{}'.format(host, port),
            access_key=access_key,
            secret_key=secret_key,
            secure=verify_ssl
        )

    # writes the initial storage bucket to storage via minio.
    def create_root_storage(self, bucket='archive', region='us-east-1'):
        try:
            self.minio_client.make_bucket(bucket, location=region)
            self.minio_client.set_bucket_policy(bucket, '*', "readonly")

        # todo should only pass or raise
        except BucketAlreadyOwnedByYou:
            pass
        except BucketAlreadyExists:
            pass
        except ResponseError:
            raise

    # Writes a file to storage will gzip if not compressed already
    def write_file(self, bucket, path, data, reduced_redundancy=False, gzipped=False):
        if not gzipped:
            out = BytesIO()
            with gzip.GzipFile(fileobj=out, mode='w', compresslevel=9) as gz:
                gz.write(data)
        else:
            out = BytesIO(data)

        try:
            # get file size
            out.seek(0, os.SEEK_END)
            out_size = out.tell()

            # reset pos for minio reading.
            out.seek(0)

            headers = {'Content-Encoding': 'gzip'}
            if reduced_redundancy:
                headers['x-amz-storage-class'] = 'REDUCED_REDUNDANCY'
            self.minio_client.put_object(
                bucket, path, out, out_size,
                metadata=headers,
                content_type='text/plain')

        except ResponseError:
            raise
    """
        Retrieves object from path, appends data, writes back to path.
    """
    def append_to_file(self, bucket, path, data):
        try:
            file_contents = '\n'.join((self.read_file(bucket, path), data))
            self.write_file(bucket, path, file_contents)
        except ResponseError:
            raise

    def read_file(self, bucket, url):
        try:
            req = self.minio_client.get_object(bucket, url)
            data = BytesIO()
            for d in req.stream(32*1024):
                data.write(d)

            data.seek(0)
            return data.getvalue()

        except ResponseError:
            raise
        except minio.error.NoSuchKey:
            log.exception("Cannot find object %s in bucket %s", url, bucket)
            raise

    """
        Deletes file url in specified bucket.
        Return true on successful
        deletion, returns a ResponseError otherwise.
    """
    def delete_file(self, bucket, url):
        try:
            # delete a file given a bucket name and a url
            self.minio_client.remove_object(bucket, url)

            return True
        except ResponseError:
            raise

    def delete_files(self, bucket, urls=[]):
        try:
            for del_err in self.minio_client.remove_objects(bucket, urls):
                print("Deletion error: {}".format(del_err))
        except ResponseError:
            raise

    def list_folder_contents(self, bucket, prefix=None, recursive=True):
        return self.minio_client.list_objects_v2(bucket, prefix, recursive)

    # TODO remove this function -- just using it for output during testing.
    def write(self, string, silence=False):
        if not silence:
            sys.stdout.write((string or '') + '\n')
