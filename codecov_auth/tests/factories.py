import factory
from factory.django import DjangoModelFactory
from codecov_auth import models
from django.utils import timezone


class OwnerFactory(DjangoModelFactory):
    class Meta:
        model = models.Owner

    name = factory.Faker('name')
    username = factory.Faker('user_name')
    plan_activated_users = []
    errors = []
    admins = []
    permission = []
    free = 0


class SessionFactory(DjangoModelFactory):
    class Meta:
        model = models.Session

    owner = factory.SubFactory(OwnerFactory)
    lastseen = timezone.now()
