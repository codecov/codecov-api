from django.test import SimpleTestCase
from asgiref.sync import sync_to_async

from ..mutation import wrap_error_handling_mutation

from graphql_api.commands.exceptions import (
    Unauthenticated,
    ValidationError,
    Unauthorized,
    NotFound,
)


class HelperMutationTest(SimpleTestCase):
    async def test_mutation_when_everything_is_good(self):
        @wrap_error_handling_mutation
        @sync_to_async
        def resolver():
            return "5"

        assert await resolver() == "5"

    async def test_mutation_when_unauthenticated_is_raised(self):
        @wrap_error_handling_mutation
        @sync_to_async
        def resolver():
            raise Unauthenticated()

        assert await resolver() == {"error": "unauthenticated"}

    async def test_mutation_when_unauthorized_is_raised(self):
        @wrap_error_handling_mutation
        @sync_to_async
        def resolver():
            raise Unauthorized()

        assert await resolver() == {"error": "unauthorized"}

    async def test_mutation_when_validation_is_raised(self):
        @wrap_error_handling_mutation
        @sync_to_async
        def resolver():
            raise ValidationError("bad data you gave me")

        assert await resolver() == {"error": "bad data you gave me"}

    async def test_mutation_when_not_found_is_raised(self):
        @wrap_error_handling_mutation
        @sync_to_async
        def resolver():
            raise NotFound()

        assert await resolver() == {"error": "not found"}
