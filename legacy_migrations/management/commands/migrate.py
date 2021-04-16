from django.core.management.base import BaseCommand, CommandError
from django.core.management.commands.migrate import Command as MigrateCommand
from django.conf import settings


class Command(MigrateCommand):
    """
    We need to override the base Django migrate command to handle the legacy migrations we have in the "legacy_migrations" app.
    Those migrations are the source of truth for the initial db state, which is captured in Django migrations 0001 for the
    core, codecov_auth and reports apps. Thus we need to fake out the initial migrations for those apps to apply duplicate migration
    steps eg. creating the same table twice.  The source of truth for all other state is captured in the standard Django migrations
    and can be safely applied after runnin the legacy migrations.
    """

    def handle(self, *args, **options):
        if len(args) == 0:
            options["run_syncdb"] = False

            codecov_auth_options = {**options}
            codecov_auth_options["fake"] = True
            codecov_auth_options["app_label"] = "codecov_auth"
            codecov_auth_options["migration_name"] = "0001"

            core_options = {**options}
            core_options["fake"] = True
            core_options["app_label"] = "core"
            core_options["migration_name"] = "0001"

            reports_options = {**options}
            reports_options["fake"] = True
            reports_options["app_label"] = "reports"
            reports_options["migration_name"] = "0001"

            legacy_options = {**options}
            legacy_options["app_label"] = "legacy_migrations"
            legacy_options["migration_name"] = None

            super().handle(*args, **codecov_auth_options)
            super().handle(*args, **core_options)
            super().handle(*args, **reports_options)
            super().handle(*args, **legacy_options)
            super().handle(*args, **options)
        else:
            super().handle(*args, **options)
