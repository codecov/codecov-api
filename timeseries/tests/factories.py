import random
from datetime import datetime

import factory
from factory.django import DjangoModelFactory

from timeseries import models


class MeasurementFactory(DjangoModelFactory):
    class Meta:
        model = models.Measurement

    owner_id = 1
    repo_id = 1
    name = "testing"
    branch = "master"
    value = factory.LazyAttribute(lambda _: random.random() * 1000)
    timestamp = factory.LazyAttribute(lambda _: datetime.now())
