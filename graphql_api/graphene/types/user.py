from graphene_django import DjangoObjectType

from codecov_auth.models import Owner


class OwnerType(DjangoObjectType):
    class Meta:
        model = Owner
        fields = ("username", "name", "student")
