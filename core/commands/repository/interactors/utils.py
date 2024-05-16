from shared.encryption.yaml_secret import yaml_secret_encryptor


def encode_secret_string(value) -> str:
    encryptor = yaml_secret_encryptor
    return "secret:%s" % encryptor.encode(value).decode()
