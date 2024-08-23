from django.apps import AppConfig


class CodecovAuthConfig(AppConfig):
    name = "codecov_auth"

    def ready(self):
        import codecov_auth.signals  # noqa: F401
