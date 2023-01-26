from rest_framework import serializers


class ComponentSerializer(serializers.Serializer):
    component_id = serializers.CharField(label="component id")
    name = serializers.CharField(label="component name")
