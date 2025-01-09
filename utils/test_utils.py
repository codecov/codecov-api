from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase
from django.test.client import Client as DjangoClient
from rest_framework.test import APIClient as DjangoAPIClient

from codecov_auth.models import Owner


class BaseTestCase(object):
    pass


class ClientMixin:
    def force_login_owner(self, owner: Owner):
        self.force_login(user=owner.user)
        session = self.session
        session["current_owner_id"] = owner.pk
        session.save()

    def logout(self):
        session = self.session
        session["current_owner_id"] = None
        session.save()
        super().logout()


class Client(ClientMixin, DjangoClient):
    pass


class APIClient(ClientMixin, DjangoAPIClient):
    pass


class TestMigrations(TestCase):
    @property
    def app(self):
        return apps.get_containing_app_config(type(self).__module__).name

    migrate_from = None
    migrate_to = None

    def setUp(self):
        assert self.migrate_from and self.migrate_to, (
            "TestCase '{}' must define migrate_from and migrate_to properties".format(
                type(self).__name__
            )
        )
        self.migrate_from = [(self.app, self.migrate_from)]
        self.migrate_to = [(self.app, self.migrate_to)]
        executor = MigrationExecutor(connection)
        old_apps = executor.loader.project_state(self.migrate_from).apps

        # Reverse to the original migration
        executor.migrate(self.migrate_from)

        self.setUpBeforeMigration(old_apps)

        # Run the migration to test
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()  # reload.
        executor.migrate(self.migrate_to)

        self.apps = executor.loader.project_state(self.migrate_to).apps

    def setUpBeforeMigration(self, apps):
        pass
