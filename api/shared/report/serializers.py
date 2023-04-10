import math

from rest_framework import serializers

from services.path import Dir


class TreeSerializer(serializers.Serializer):
    name = serializers.CharField()
    full_path = serializers.CharField()
    coverage = serializers.FloatField()
    lines = serializers.IntegerField()
    hits = serializers.IntegerField()
    partials = serializers.IntegerField()
    misses = serializers.IntegerField()

    def to_representation(self, instance):
        depth = self.context.get("depth", 1)
        max_depth = self.context.get("max_depth", math.inf)
        res = super().to_representation(instance)
        if isinstance(instance, Dir):
            if depth < max_depth:
                res["children"] = TreeSerializer(
                    instance.children,
                    many=True,
                    context={
                        "depth": depth + 1,
                        "max_depth": max_depth,
                    },
                ).data
        return res
