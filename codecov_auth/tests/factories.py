from uuid import uuid4

import factory
from factory.django import DjangoModelFactory
from codecov_auth import models
from django.utils import timezone

from utils.encryption import encode


class OwnerFactory(DjangoModelFactory):
    class Meta:
        model = models.Owner
        exclude = ('unencrypted_oauth_token',)

    name = factory.Faker('name')
    username = factory.Faker('user_name')
    plan_activated_users = []
    errors = []
    admins = []
    permission = []
    free = 0
    unencrypted_oauth_token = factory.LazyFunction(lambda: uuid4().hex)

    oauth_token = factory.LazyAttribute(lambda o: encode(o.unencrypted_oauth_token))


class SessionFactory(DjangoModelFactory):
    class Meta:
        model = models.Session

    owner = factory.SubFactory(OwnerFactory)
    lastseen = timezone.now()
