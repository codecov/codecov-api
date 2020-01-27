from uuid import uuid4

import factory
from factory.django import DjangoModelFactory
from codecov_auth.models import Owner, Session
from django.utils import timezone

from utils.encryption import encryptor


class OwnerFactory(DjangoModelFactory):
    class Meta:
        model = Owner
        exclude = ('unencrypted_oauth_token',)

    name = factory.Faker('name')
    username = factory.Faker('user_name')
    service = 'github'
    service_id='1234'
    plan_activated_users = []
    admins = []
    permission = []
    free = 0
    unencrypted_oauth_token = factory.LazyFunction(lambda: uuid4().hex)
    cache = { "stats": { "repos": 1, "members": 2 }}
    oauth_token = factory.LazyAttribute(lambda o: encryptor.encode(o.unencrypted_oauth_token).decode())


class SessionFactory(DjangoModelFactory):
    class Meta:
        model = Session

    owner = factory.SubFactory(OwnerFactory)
    lastseen = timezone.now()
