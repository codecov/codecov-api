import uuid

from django.db import models
from django.contrib.postgres.fields import CITextField, JSONField, ArrayField

# Create your models here.


class Owner(models.Model):

    class Meta:
        db_table = 'owners'

    REQUIRED_FIELDS = []
    USERNAME_FIELD = 'username'

    ownerid = models.AutoField(primary_key=True)
    # service
    username = CITextField(null=True, unique=True)
    email = models.TextField(null=True)
    name = models.TextField(null=True)
    oauth_token = models.TextField(null=True)
    stripe_customer_id = models.TextField(null=True)
    stripe_subscription_id = models.TextField(null=True)
    trial = models.BooleanField(null=True)
    createstamp = models.DateTimeField(auto_now_add=True)
    service_id = models.TextField()
    private_access = models.BooleanField(null=True)
    staff = models.BooleanField(null=True, default=False)
    cache = JSONField(null=True)
    # plan
    # plan_provider
    plan_user_count = models.SmallIntegerField(null=True)
    plan_auto_activate = models.BooleanField(null=True)
    plan_activated_users = ArrayField(models.IntegerField(null=True))
    did_trial = models.BooleanField(null=True)
    free = models.SmallIntegerField()
    invoice_details = models.TextField(null=True)
    errors = ArrayField(models.TextField(null=True), null=True)
    delinquent = models.BooleanField(null=True)
    yaml = JSONField(null=True)
    updatestamp = models.DateTimeField(auto_now=True)
    organizations = ArrayField(models.IntegerField(null=True), null=True)
    admins = ArrayField(models.IntegerField(null=True), null=True)
    integration_id = models.IntegerField(null=True)
    permission = ArrayField(models.IntegerField(null=True), null=True)
    bot = models.IntegerField(null=True)

    @property
    def is_anonymous(self):
        return False

    @property
    def is_authenticated(self):
        return False


class Session(models.Model):

    class Meta:
        db_table = 'sessions'

    sessionid = models.AutoField(primary_key=True)
    token = models.UUIDField(default=uuid.uuid4, editable=False)
    name = models.TextField()
    useragent = models.TextField()
    ip = models.TextField()
    owner = models.ForeignKey('Owner', db_column='ownerid', on_delete=models.CASCADE)
    lastseen = models.DateTimeField()
    # type
