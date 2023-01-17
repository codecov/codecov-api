from asgiref.sync import sync_to_async

from codecov.commands.base import BaseInteractor
from services.yaml import final_commit_yaml


class GetFinalYamlInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, commit):
        return final_commit_yaml(commit, self.current_user).to_dict()
