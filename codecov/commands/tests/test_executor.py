from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from django.urls import ResolverMatch

from codecov_auth.commands.owner import OwnerCommands

from ..executor import get_executor_from_command, get_executor_from_request


def test_get_executor_from_request():
    request_factory = RequestFactory()
    request = request_factory.get("")
    request.current_owner = None
    match = ResolverMatch(func=lambda: None, args=(), kwargs={"service": "gh"})
    request.resolver_match = match
    request.user = AnonymousUser()
    executor = get_executor_from_request(request)
    assert executor.service == "github"
    assert executor.current_owner is None


def test_get_executor_from_command():
    command = OwnerCommands(None, "github")
    executor = get_executor_from_command(command)
    assert executor.service == "github"
    assert executor.current_owner is None
