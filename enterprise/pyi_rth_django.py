import django.core.management
import django.utils.autoreload


def _get_commands():
    # Django groupss commands by app.
    # This returns static dict() as it is for django 1.8 and the default project.
    commands = {
        "runserver": "django.core",
        "migrate": "legacy_migrations",
        "shell": "django.core",
        "collectstatic": "django.contrib.staticfiles",
    }
    return commands


_old_restart_with_reloader = django.utils.autoreload.restart_with_reloader


def _restart_with_reloader(*args):
    import sys

    a0 = sys.argv.pop(0)
    try:
        return _old_restart_with_reloader(*args)
    finally:
        sys.argv.insert(0, a0)


# Override get_commands() function otherwise the app will complain that
# there are no commands.
django.core.management.get_commands = _get_commands
# Override restart_with_reloader() function otherwise the app might
# complain that some commands do not exist. e.g. runserver.
django.utils.autoreload.restart_with_reloader = _restart_with_reloader
