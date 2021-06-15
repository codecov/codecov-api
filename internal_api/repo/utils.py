from shared.encryption.standard import StandardEncryptor
from django.conf import settings


def encode_secret_string(value):
    ## Reminder -- this should probably be rewritten to reuse the same code
    ## as in the new worker, whenever the API starts using the new worker.
    encryptor = StandardEncryptor()
    encryptor.key = settings.YAML_SECRET_KEY
    return "secret:%s" % encryptor.encode(value).decode()
