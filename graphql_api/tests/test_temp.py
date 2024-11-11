import ast
import inspect
from typing import List

import pytest
from django.db import models

from graphql_api.types import query  # Import the Ariadne QueryType with resolvers

# List of known synchronous functions that should be wrapped in sync_to_async in async functions
SYNC_FUNCTIONS_TO_WRAP = {"get", "filter", "create", "update", "delete", "sleep"}


def is_function_wrapped_in_sync_to_async(node: ast.Call) -> bool:
    """
    Check if a function call is wrapped in sync_to_async.
    """
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "sync_to_async"
    )


def is_django_model_method_call(node: ast.Attribute) -> bool:
    """
    Check if a given node is a method call on a Django model.
    """
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        model_name = node.value.id
        # Attempt to get the actual model class from the globals if available
        model_class = globals().get(model_name)
        # Check if it’s a Django model class
        return inspect.isclass(model_class) and issubclass(model_class, models.Model)
    return False


def find_unwrapped_sync_calls_in_function(func) -> List[str]:
    """
    Parse a function to find sync calls on Django models that aren't wrapped in sync_to_async.
    """
    unwrapped_sync_calls = []

    # Get the AST of the function's source code
    try:
        source = inspect.getsource(func)
    except (OSError, TypeError, IndentationError):
        print(f"Could not retrieve or parse source for {func.__name__}. Skipping.")
        return unwrapped_sync_calls  # Return empty list if source can't be accessed

    tree = ast.parse(source)

    # Traverse the AST to find unwrapped Django model method calls
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            # Check if this is a Django model method call that isn’t wrapped in sync_to_async
            if is_django_model_method_call(
                node.func
            ) and not is_function_wrapped_in_sync_to_async(node):
                unwrapped_sync_calls.append(node.func.attr)
    return unwrapped_sync_calls


# Retrieve only Ariadne resolvers for testing
def get_ariadne_resolvers():
    """
    Retrieve all Ariadne resolvers from a specified QueryType or MutationType.
    """
    # Ensure `query` is a QueryType or MutationType instance
    if hasattr(query, "_resolvers") and isinstance(query._resolvers, dict):
        return list(query._resolvers.values())
    else:
        print(
            "The object `query` does not contain _resolvers. Ensure it is a QueryType or MutationType."
        )
        return []


# Only test Ariadne resolvers
ariadne_resolvers_to_test = get_ariadne_resolvers()


@pytest.mark.parametrize("func", ariadne_resolvers_to_test)
def test_functions_have_wrapped_sync_calls(func):
    unwrapped_calls = find_unwrapped_sync_calls_in_function(func)
    assert not unwrapped_calls, (
        f"The following Django model method calls are missing `sync_to_async` in {func.__name__}: "
        f"{', '.join(unwrapped_calls)}"
    )
