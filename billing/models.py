from django.db import models

from billing.constants import FREE_PLAN_NAME

# Create your models here.
from codecov.models import BaseCodecovModel


class PlanProviders(models.TextChoices):
    GITHUB = "github"


class Account(BaseCodecovModel):
    stripe_customer_id = models.TextField(null=True)
    stripe_subscription_id = models.TextField(null=True)
    plan = models.TextField(default=FREE_PLAN_NAME)
    plan_provider = models.TextField(null=True, choices=PlanProviders.choices)
    max_activated_user_count = models.SmallIntegerField(default=5)
    should_auto_activate_users = models.BooleanField(default=True)
