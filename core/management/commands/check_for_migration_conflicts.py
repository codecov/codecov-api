import os

from django.apps import apps
from django.core.management.base import (
    BaseCommand,
    CommandError,
    no_translations,
)


class Command(BaseCommand):
    def handle(self, *args, **options):
        conflicts_found = False
        for app in apps.get_app_configs():
            try:
                migrations = os.listdir(f"{app.name}/migrations")
                migrations_by_prefix = {}
                for migration in migrations:
                    # If it doesn't end in .py it's not a migration file
                    if not migration.endswith(".py"):
                        continue

                    prefix = migration[0:4]
                    migrations_by_prefix.setdefault(prefix, []).append(migration)

                for prefix, grouped_migrations in migrations_by_prefix.items():
                    if len(grouped_migrations) > 1:
                        conflicts_found = True
                        print(
                            f"Conflict found in migrations for {app.name} with prefix {prefix}:"
                        )
                        for grouped_migration in grouped_migrations:
                            print(grouped_migration)
                        print()
            # It's expected to not find migration folders for Django/3rd party apps
            except FileNotFoundError:
                pass

        if conflicts_found:
            raise Exception("Found conflicts in migrations.")
        else:
            print("No conflicts found!")
