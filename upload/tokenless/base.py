from rest_framework.exceptions import NotFound

class BaseTokenlessUploadHandler(object):
    def __init__(self, upload_params):
        self.upload_params = upload_params

    def check_repository_type(self, repository_type):
        if repository_type.lower() not in ('github', 'gitlab', 'bitbucket'):
            raise NotFound('Sorry this service is not supported. Codecov currently only works with GitHub, GitLab, and BitBucket repositories')
        return repository_type.lower()
