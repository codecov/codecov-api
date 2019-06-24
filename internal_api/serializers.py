from rest_framework import serializers
from codecov_auth.models import Owner


class AuthorSerializer(serializers.ModelSerializer):
    ownerid = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.CharField()
    name = serializers.CharField()

    class Meta:
        model = Owner
        fields = ('ownerid', 'username', 'email', 'name')
