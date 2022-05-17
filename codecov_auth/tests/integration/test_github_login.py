import pytest
import vcr
import urllib3
import re
from django.urls import reverse
from unittest.mock import patch
import urllib3
from bs4 import BeautifulSoup
import codecov_auth.views as auth_views



@vcr.use_cassette('codecov_auth/tests/integration/cassetes/test_github_login_redirect.yml', record_mode="once")
def test_github_login_redirect(client, settings, mocker):
    settings.IS_ENTERPRISE = False
    # We need to fix the state so VCR can playback the episode.
    state = 'b57f05d5fcee497595af4024c8f106e3'
    mocker.patch.object(auth_views.GithubLoginView, 'generate_state', side_effect=lambda *args: state)
    url = reverse("github-login")
    res = client.get(url)
    assert res.status_code == 302
    assert (
        res.url
        == f"https://github.com/login/oauth/authorize?response_type=code&scope=user%3Aemail%2Cread%3Aorg%2Crepo%3Astatus%2Cwrite%3Arepo_hook&client_id=3d44be0e772666136a13&state={state}"
    )
    # Now we check that the rendered page that /login/gh takes us to is really the one we expect.
    # Which is a login page for GitHub
    http = urllib3.PoolManager()
    res = http.request('GET', res.url)
    assert res.status == 200
    soup = BeautifulSoup(res.data)
    # Title
    assert soup.title.string == 'Sign in to GitHub \xB7 GitHub'
    # The description for the user is correct
    assert re.search(r'Sign in to GitHub +to continue to Codecov', soup.get_text().replace("\n", ""))
    # The auth info we passed is there (to be visited after login)
    return_to_input = soup.find(id="return_to")
    assert return_to_input.attrs['value'] == "/login/oauth/authorize?client_id=3d44be0e772666136a13&response_type=code&scope=user%3Aemail%2Cread%3Aorg%2Crepo%3Astatus%2Cwrite%3Arepo_hook&state=b57f05d5fcee497595af4024c8f106e3"
    # Client id matches
    client_id_input = soup.find(id="client_id")
    assert client_id_input.attrs['value'] == "3d44be0e772666136a13"
    # There is login / password and submit button
    assert soup.find(id="password") and soup.find(id="password").name == "input"
    assert soup.find(id="login_field") and soup.find(id="login_field").name == "input"
    assert soup.find(type="submit") and soup.find(type="submit").name == "input" and soup.find(type="submit").attrs['value'] == "Sign in"
