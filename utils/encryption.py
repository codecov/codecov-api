import os
import hashlib

from django.conf import settings
from Crypto import Random
from Crypto.Cipher import AES
from base64 import b64encode, b64decode

first_part = settings.ENCRYPTION_SECRET
second_part = os.getenv('ENCRYPTION_SECRET', '')
third_part = 'fYaA^Bj&h89,hs49iXyq]xARuCg'

joined = ''.join(
    [
        first_part,
        second_part,
        third_part
    ]
)

KEY = hashlib.sha256(
    joined.encode()
).digest()

BS = 16


def unpad(s):
    return s[:-ord(s[len(s)-1:])]


def pad(s):
    return s + (BS - len(s) % BS) * chr(BS - len(s) % BS)


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
    return unpad(cipher.decrypt(string[16:])).decode()


def encode(string):
    iv = Random.new().read(AES.block_size)
    des = AES.new(KEY, AES.MODE_CBC, iv)
    return b64encode(iv + des.encrypt(pad(string).encode()))
