import uuid
from typing import Any


def is_uuid(value: Any) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False
