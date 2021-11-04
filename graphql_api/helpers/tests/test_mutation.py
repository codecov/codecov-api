from asgiref.sync import sync_to_async
from django.test import SimpleTestCase

from codecov.commands.exceptions import (
    NotFound,
    Unauthenticated,
    Unauthorized,
    ValidationError,
)

from ..mutation import resolve_union_error_type, wrap_error_handling_mutation


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

        resolved_value = await resolver()
        assert resolved_value["error"].message == "You are not authenticated"
        graphql_type_error = resolve_union_error_type(resolved_value["error"])
        assert graphql_type_error == "UnauthenticatedError"

    async def test_mutation_when_unauthorized_is_raised(self):
        @wrap_error_handling_mutation
        @sync_to_async
        def resolver():
            raise Unauthorized()

        resolved_value = await resolver()
        assert resolved_value["error"].message == "You are not authorized"
        graphql_type_error = resolve_union_error_type(resolved_value["error"])
        assert graphql_type_error == "UnauthorizedError"

    async def test_mutation_when_validation_is_raised(self):
        @wrap_error_handling_mutation
        @sync_to_async
        def resolver():
            raise ValidationError("wrong data")

        resolved_value = await resolver()
        assert resolved_value["error"].message == "wrong data"
        graphql_type_error = resolve_union_error_type(resolved_value["error"])
        assert graphql_type_error == "ValidationError"

    async def test_mutation_when_not_found_is_raised(self):
        @wrap_error_handling_mutation
        @sync_to_async
        def resolver():
            raise NotFound()

        resolved_value = await resolver()
        assert resolved_value["error"].message == "Cant find the requested resource"
        graphql_type_error = resolve_union_error_type(resolved_value["error"])
        assert graphql_type_error == "NotFoundError"

    async def test_mutation_when_random_exception_is_raised_it_reraise(self):
        @wrap_error_handling_mutation
        @sync_to_async
        def resolver():
            raise AttributeError()

        with self.assertRaises(AttributeError):
            resolved_value = await resolver()
