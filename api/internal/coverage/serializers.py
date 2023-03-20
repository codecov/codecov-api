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
        res = super().to_representation(instance)
        if isinstance(instance, Dir):
            res["children"] = TreeSerializer(instance.children, many=True).data
        return res
