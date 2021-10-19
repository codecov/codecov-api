import os


def get_current_version() -> str:
    return os.getenv("RELEASE_VERSION", "NO_VERSION")
