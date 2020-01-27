import requests

from codecov_auth.constants import GITLAB_BASE_URL

GITLAB_PAYLOAD_AVATAR_URL_KEY = 'avatar_url'

def get_gitlab_url(email, size):
    res = requests.get('{}/api/v4/avatar?email={}&size={}'.format(GITLAB_BASE_URL, email, size))
    url = ''
    if res.status_code == 200:
        data = res.json()
        try:
            url = data[GITLAB_PAYLOAD_AVATAR_URL_KEY]
        except KeyError:
            pass

    return url
