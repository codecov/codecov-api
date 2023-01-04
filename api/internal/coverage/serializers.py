from rest_framework import serializers

from services.path import File


class RecursiveField(serializers.Serializer):
    def to_representation(self, value):
        serializer = self.parent.parent.__class__(value, context=self.context)
        return serializer.data


class TreeSerializer(serializers.Serializer):
    name = serializers.CharField()
    full_path = serializers.CharField()
    coverage = serializers.FloatField()
    lines = serializers.IntegerField()
    hits = serializers.IntegerField()
    partials = serializers.IntegerField()
    misses = serializers.IntegerField()
    children = RecursiveField(many=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if isinstance(self.instance, File):
            # only dirs have children
            self.fields.pop("children")
