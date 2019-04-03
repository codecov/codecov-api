from rest_framework import serializers
from .models import Pull
from codecov_auth.models import Owner


class PullAuthorSerializer(serializers.ModelSerializer):
    username = serializers.CharField()
    email = serializers.CharField()
    name = serializers.CharField()

    class Meta:
        model = Owner
        fields = ('username', 'email', 'name')

class PullSerializer(serializers.ModelSerializer):
    state = serializers.CharField()
    title = serializers.CharField()
    base = serializers.CharField()
    compared_to = serializers.CharField()
    head = serializers.CharField()
    diff = serializers.JSONField()
    flare = serializers.JSONField()
    author = PullAuthorSerializer()

    class Meta:
        model = Pull
        fields = '__all__'