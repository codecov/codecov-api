import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from codecov_auth.models import DjangoSession


class DjangoSessionFactory(DjangoModelFactory):
    class Meta:
        model = DjangoSession

    expire_date = timezone.now()
    session_key = factory.Faker("uuid4")
