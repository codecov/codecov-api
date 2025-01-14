import html
from typing import Optional

import yaml
from shared.django_apps.core.models import Repository
from shared.django_apps.utils.model_utils import get_ownerid_if_member
from shared.validation.exceptions import InvalidYamlException
from shared.yaml.validation import validate_yaml

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import (
    NotFound,
    Unauthenticated,
    Unauthorized,
    ValidationError,
)
from codecov.db import sync_to_async
from codecov_auth.constants import OWNER_YAML_TO_STRING_KEY
from codecov_auth.helpers import current_user_part_of_org
from codecov_auth.models import Owner


class SetYamlOnOwnerInteractor(BaseInteractor):
    def validate(self) -> None:
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

    def authorize(self) -> None:
        if not current_user_part_of_org(self.current_owner, self.owner):
            raise Unauthorized()

    def get_owner(self, username: str) -> Owner:
        try:
            return Owner.objects.get(username=username, service=self.service)
        except Owner.DoesNotExist:
            raise NotFound()

    def convert_yaml_to_dict(self, yaml_input: str) -> Optional[dict]:
        yaml_safe = html.escape(yaml_input, quote=False)
        try:
            yaml_dict = yaml.safe_load(yaml_safe)
        except yaml.scanner.ScannerError as e:
            line = e.problem_mark.line
            column = e.problem_mark.column
            message = (
                f"Syntax error at line {line + 1}, column {column + 1}: {e.problem}"
            )
            raise ValidationError(message)
        if not yaml_dict:
            return None
        try:
            return validate_yaml(yaml_dict, show_secrets_for=None)
        except InvalidYamlException as e:
            message = f"Error at {str(e.error_location)}: {e.error_message}"
            raise ValidationError(message)

    def yaml_side_effects(self, old_yaml: dict | None, new_yaml: dict | None) -> None:
        old_yaml_branch = old_yaml and old_yaml.get("codecov", {}).get("branch")
        new_yaml_branch = new_yaml and new_yaml.get("codecov", {}).get("branch")

        # Update all repositories from owner if branch is updated in yaml
        if new_yaml_branch != old_yaml_branch:
            repos = Repository.objects.filter(author_id=self.owner.ownerid)
            repos.update(
                branch=new_yaml_branch or old_yaml_branch
            )  # Keeps old_branch if new_branch is None

        old_yaml_bot = old_yaml and old_yaml.get("codecov", {}).get("bot")
        new_yaml_bot = new_yaml and new_yaml.get("codecov", {}).get("bot")

        # Update owner's bot column if bot is updated in yaml
        if new_yaml_bot != old_yaml_bot:
            new_bot = (
                get_ownerid_if_member(
                    service=self.owner.service,
                    owner_username=new_yaml_bot,
                    owner_id=self.owner.ownerid,
                )
                or old_yaml_bot
                or None
            )
            self.owner.bot = new_bot
            self.owner.save()

    @sync_to_async
    def execute(self, username: str, yaml_input: str) -> Owner:
        self.validate()
        self.owner = self.get_owner(username)
        self.authorize()
        old_yaml = self.owner.yaml
        self.owner.yaml = self.convert_yaml_to_dict(yaml_input)
        if self.owner.yaml:
            self.owner.yaml[OWNER_YAML_TO_STRING_KEY] = yaml_input
        self.owner.save()

        # side effects
        self.yaml_side_effects(old_yaml=old_yaml, new_yaml=self.owner.yaml)
        return self.owner
