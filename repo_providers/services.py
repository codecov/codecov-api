from torngit import get
from utils.encryption import encryptor


class RepoProviderService(object):

    def get_adapter(self, owner, repo):
        adapter_params = dict(
            repo=dict(name=repo.name),
            owner=dict(username=repo.author.username),
            token=encryptor.decrypt_token(owner.oauth_token)
        )
        return get(
            'github',
            **adapter_params
        )
