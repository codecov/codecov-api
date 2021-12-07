from django.conf import settings
from django.db import migrations

"""
These classes can be used to skip altering DB state while maintaing the state of migrations.
To use them you should manually replace the migration step in the migration file with its
corresponding "Risky" migration step.
Not all migration steps (such as AddField) are represented here because they cannot safely
exist in code while not being applied in the DB.
"""


class RiskyRemoveField(migrations.RemoveField):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if settings.SKIP_RISKY_MIGRATION_STEPS:
            return

        super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if settings.SKIP_RISKY_MIGRATION_STEPS:
            return

        super().database_backwards(app_label, schema_editor, from_state, to_state)


class RiskyAlterUniqueTogether(migrations.AlterUniqueTogether):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if settings.SKIP_RISKY_MIGRATION_STEPS:
            return

        super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if settings.SKIP_RISKY_MIGRATION_STEPS:
            return

        super().database_backwards(app_label, schema_editor, from_state, to_state)


class RiskyAlterIndexTogether(migrations.AlterIndexTogether):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if settings.SKIP_RISKY_MIGRATION_STEPS:
            return

        super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if settings.SKIP_RISKY_MIGRATION_STEPS:
            return

        super().database_backwards(app_label, schema_editor, from_state, to_state)


class RiskyAddIndex(migrations.AddIndex):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if settings.SKIP_RISKY_MIGRATION_STEPS:
            return

        super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if settings.SKIP_RISKY_MIGRATION_STEPS:
            return

        super().database_backwards(app_label, schema_editor, from_state, to_state)


class RiskyRemoveIndex(migrations.RemoveIndex):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if settings.SKIP_RISKY_MIGRATION_STEPS:
            return

        super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if settings.SKIP_RISKY_MIGRATION_STEPS:
            return

        super().database_backwards(app_label, schema_editor, from_state, to_state)


class RiskyAddConstraint(migrations.AddConstraint):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if settings.SKIP_RISKY_MIGRATION_STEPS:
            return

        super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if settings.SKIP_RISKY_MIGRATION_STEPS:
            return

        super().database_backwards(app_label, schema_editor, from_state, to_state)


class RiskyRemoveConstraint(migrations.RemoveConstraint):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if settings.SKIP_RISKY_MIGRATION_STEPS:
            return

        super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if settings.SKIP_RISKY_MIGRATION_STEPS:
            return

        super().database_backwards(app_label, schema_editor, from_state, to_state)


class RiskyRunSQL(migrations.RunSQL):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if settings.SKIP_RISKY_MIGRATION_STEPS:
            return

        super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if settings.SKIP_RISKY_MIGRATION_STEPS:
            return

        super().database_backwards(app_label, schema_editor, from_state, to_state)


class RiskyRunPython(migrations.RunPython):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if settings.SKIP_RISKY_MIGRATION_STEPS:
            return

        super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if settings.SKIP_RISKY_MIGRATION_STEPS:
            return

        super().database_backwards(app_label, schema_editor, from_state, to_state)
