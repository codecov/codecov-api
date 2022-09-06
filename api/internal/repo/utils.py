from django.conf import settings
from shared.encryption.yaml_secret import yaml_secret_encryptor


def encode_secret_string(value):
    ## Reminder -- this should probably be rewritten to reuse the same code
    ## as in the new worker, whenever the API starts using the new worker.
    encryptor = yaml_secret_encryptor
    return "secret:%s" % encryptor.encode(value).decode()
