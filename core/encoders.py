from dataclasses import astuple, is_dataclass

from django.core.serializers.json import DjangoJSONEncoder


class ReportJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if is_dataclass(obj):
            return astuple(obj)
        return super().default(self, obj)
