import gzip
import logging
import os
import sys
from datetime import timedelta
from io import BytesIO

import minio
from minio.credentials import Chain, Credentials, EnvAWS, EnvMinio, IAMProvider
from minio.error import BucketAlreadyExists, BucketAlreadyOwnedByYou, ResponseError

from utils.config import get_config

log = logging.getLogger(__name__)


MINIO_CLIENT = None


# Service class for interfacing with codecov's underlying storage layer, minio
class StorageService(object):
    def __init__(self, in_config=None):
        global MINIO_CLIENT

        # init minio
        if in_config is None:
            self.minio_config = get_config("services", "minio", default={})
        else:
            self.minio_config = in_config

        if "host" not in self.minio_config:
            self.minio_config["host"] = "minio"
        if "port" not in self.minio_config:
            self.minio_config["port"] = 9000
        if "iam_auth" not in self.minio_config:
            self.minio_config["iam_auth"] = False
        if "iam_endpoint" not in self.minio_config:
            self.minio_config["iam_endpoint"] = None

        if not MINIO_CLIENT:
            MINIO_CLIENT = self.init_minio_client(
                self.minio_config["host"],
                self.minio_config["port"],
                self.minio_config["access_key_id"],
                self.minio_config["secret_access_key"],
                self.minio_config["verify_ssl"],
                self.minio_config["iam_auth"],
                self.minio_config["iam_endpoint"],
            )
            log.info("----- created minio_client: ---- ")

    def client(self):
        return MINIO_CLIENT if MINIO_CLIENT else None

    def init_minio_client(
        self,
        host,
        port,
        access_key,
        secret_key,
        verify_ssl,
        iam_auth=False,
        iam_endpoint=None,
    ):
        host = "{}:{}".format(host, port)
        if iam_auth:
            return minio.Minio(
                host,
                secure=verify_ssl,
                credentials=Credentials(
                    provider=Chain(
                        providers=[
                            IAMProvider(endpoint=iam_endpoint),
                            EnvMinio(),
                            EnvAWS(),
                        ]
                    )
                ),
            )

        return minio.Minio(
            host, access_key=access_key, secret_key=secret_key, secure=verify_ssl,
        )

    # writes the initial storage bucket to storage via minio.
    def create_root_storage(self, bucket="archive", region="us-east-1"):
        if not MINIO_CLIENT.bucket_exists(bucket):
            MINIO_CLIENT.make_bucket(bucket, location=region)
            MINIO_CLIENT.set_bucket_policy(bucket, "*", "readonly")

    # Writes a file to storage will gzip if not compressed already
    def write_file(self, bucket, path, data, reduced_redundancy=False, gzipped=False):
        if not gzipped:
            out = BytesIO()
            with gzip.GzipFile(fileobj=out, mode="w", compresslevel=9) as gz:
                gz.write(data)
        else:
            out = BytesIO(data)

        try:
            # get file size
            out.seek(0, os.SEEK_END)
            out_size = out.tell()

            # reset pos for minio reading.
            out.seek(0)

            headers = {"Content-Encoding": "gzip"}
            if reduced_redundancy:
                headers["x-amz-storage-class"] = "REDUCED_REDUNDANCY"
            MINIO_CLIENT.put_object(
                bucket, path, out, out_size, metadata=headers, content_type="text/plain"
            )

        except ResponseError:
            raise

    """
        Retrieves object from path, appends data, writes back to path.
    """

    def append_to_file(self, bucket, path, data):
        try:
            file_contents = "\n".join((self.read_file(bucket, path), data))
            self.write_file(bucket, path, file_contents)
        except ResponseError:
            raise

    def read_file(self, bucket, url):
        try:
            req = MINIO_CLIENT.get_object(bucket, url)
            data = BytesIO()
            for d in req.stream(32 * 1024):
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
            MINIO_CLIENT.remove_object(bucket, url)

            return True
        except ResponseError:
            raise

    def delete_files(self, bucket, urls=[]):
        try:
            for del_err in MINIO_CLIENT.remove_objects(bucket, urls):
                print("Deletion error: {}".format(del_err))
        except ResponseError:
            raise

    def list_folder_contents(self, bucket, prefix=None, recursive=True):
        return MINIO_CLIENT.list_objects_v2(bucket, prefix, recursive)

    # TODO remove this function -- just using it for output during testing.
    def write(self, string, silence=False):
        if not silence:
            sys.stdout.write((string or "") + "\n")

    def create_presigned_put(self, bucket, path, expires):
        expires = timedelta(seconds=expires)
        return MINIO_CLIENT.presigned_put_object(bucket, path, expires)
