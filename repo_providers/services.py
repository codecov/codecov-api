from torngit import get


class RepoProviderService(object):

    def get_adapter(self, repo):
        return get('github', repo=repo.service_id, owner=repo.owner.username, token=None)
