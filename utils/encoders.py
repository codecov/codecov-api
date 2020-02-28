from django.core.serializers.json import DjangoJSONEncoder
from dataclasses import is_dataclass, astuple


class CustomJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if is_dataclass(obj):
            return astuple(obj)
        return super().default(self, obj)
