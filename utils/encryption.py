import os

from shared.encryption import StandardEncryptor

from django.conf import settings

first_part = settings.ENCRYPTION_SECRET
second_part = os.getenv("ENCRYPTION_SECRET", "")
third_part = "fYaA^Bj&h89,hs49iXyq]xARuCg"

encryptor = StandardEncryptor(first_part, second_part, third_part)
