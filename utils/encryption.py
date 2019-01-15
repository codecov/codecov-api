import os
import hashlib

from django.conf import settings

from Crypto.Cipher import AES
from base64 import b64decode


KEY = hashlib.sha256(
    ''.join(
        [
            settings.encryption_secret.encode(),
            os.getenv('ENCRYPTION_SECRET', '').encode(),
            'fYaA^Bj&h89,hs49iXyq]xARuCg'.encode()
        ]
    )
).digest()


def unpad(s):
    return s[:-ord(s[len(s)-1:])]


def decrypt_token(oauth_token):
    _oauth = decode(oauth_token)
    token = {}
    if ':' in _oauth:
        token['key'], token['secret'] = _oauth.split(':', 1)
    else:
        token['key'] = _oauth
        token['secret'] = None
    return token


def decode(string):
    string = b64decode(string)
    iv = string[:16]
    cipher = AES.new(KEY, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(string[16:]))
