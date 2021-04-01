from django.core.management.base import BaseCommand, CommandError
from django.core.management.commands.migrate import Command as MigrateCommand
from django.conf import settings

class Command(MigrateCommand):
    def handle(self, *args, **options):
        if len(args) == 0:
            options['run_syncdb'] = False

            core_options = {**options}
            core_options['fake'] = True
            core_options['app_label'] = 'core'
            core_options['migration_name'] = '0001'

            reports_options = {**options}
            reports_options['fake'] = True
            reports_options['app_label'] = 'reports'
            reports_options['migration_name'] = '0001'

            legacy_options = {**options}
            legacy_options['app_label'] = 'legacy_migrations'
            legacy_options['migration_name'] = None

            super().handle(*args, **core_options)
            super().handle(*args, **reports_options)
            super().handle(*args, **legacy_options)
            super().handle(*args, **options)
        else:
            super().handle(*args, **options)