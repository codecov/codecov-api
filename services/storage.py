from loguru import logger
from datetime import timedelta

from shared.storage.minio import MinioStorageService

from utils.config import get_config


MINIO_CLIENT = None


# Service class for interfacing with codecov's underlying storage layer, minio
class StorageService(MinioStorageService):
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
            logger.info("----- created minio_client: ---- ")
        self.minio_client = MINIO_CLIENT

    def create_presigned_put(self, bucket, path, expires):
        expires = timedelta(seconds=expires)
        return self.minio_client.presigned_put_object(bucket, path, expires)

    def create_presigned_get(self, bucket, path, expires):
        expires = timedelta(seconds=expires)
        return self.minio_client.presigned_get_object(bucket, path, expires)
