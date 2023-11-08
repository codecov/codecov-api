from django.db import models
from django_prometheus.models import ExportModelOperationsMixin

# Create your models here.
from codecov.models import BaseCodecovModel
from plan.constants import PlanName


class PlanProviders(models.TextChoices):
    GITHUB = "github"


class Account(ExportModelOperationsMixin("billing.account"), BaseCodecovModel):
    stripe_customer_id = models.TextField(null=True)
    stripe_subscription_id = models.TextField(null=True)
    plan = models.TextField(default=PlanName.FREE_PLAN_NAME.value)
    plan_provider = models.TextField(null=True, choices=PlanProviders.choices)
    max_activated_user_count = models.SmallIntegerField(default=5)
    should_auto_activate_users = models.BooleanField(default=True)
