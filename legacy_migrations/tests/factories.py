import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from legacy_migrations.models import YamlHistory


class YamlHistoryFactory(DjangoModelFactory):
    class Meta:
        model = YamlHistory

    timestamp = factory.LazyFunction(timezone.now)
    message = "some_message"
    source = "some source"
    diff = "some diff between things"
