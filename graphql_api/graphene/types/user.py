from graphene_django import DjangoObjectType

from codecov_auth.models import Owner


class UserType(DjangoObjectType):
    class Meta:
        model = Owner
        fields = ("username", "name", "student")
