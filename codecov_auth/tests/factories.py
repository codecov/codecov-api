from uuid import uuid4

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from codecov_auth.models import Owner, RepositoryToken, Service, Session
from utils.encryption import encryptor


class OwnerFactory(DjangoModelFactory):
    class Meta:
        model = Owner
        exclude = ("unencrypted_oauth_token",)

    name = factory.Faker("name")
    email = factory.Faker("email")
    username = factory.Faker("user_name")
    service = "github"
    service_id = factory.Sequence(lambda n: f"{n}")
    updatestamp = factory.LazyFunction(timezone.now)
    plan_activated_users = []
    admins = []
    permission = []
    free = 0
    onboarding_completed = False
    unencrypted_oauth_token = factory.LazyFunction(lambda: uuid4().hex)
    cache = {"stats": {"repos": 1, "members": 2, "users": 1}}
    oauth_token = factory.LazyAttribute(
        lambda o: encryptor.encode(o.unencrypted_oauth_token).decode()
    )


class SessionFactory(DjangoModelFactory):
    class Meta:
        model = Session

    owner = factory.SubFactory(OwnerFactory)
    lastseen = timezone.now()
    type = Session.SessionType.API.value
    token = factory.Faker("uuid4")
