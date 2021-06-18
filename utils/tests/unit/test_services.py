import os

from utils.services import get_long_service_name, get_short_service_name


class TestServices(object):
    def test_gitlab(self):
        service = get_long_service_name("gl")
        assert service == "gitlab"

        service = get_long_service_name("gitlab")
        assert service == "gitlab"

        service = get_short_service_name("gitlab")
        assert service == "gl"

        service = get_short_service_name("gl")
        assert service == "gl"

    def test_bb(self):
        service = get_long_service_name("bb")
        assert service == "bitbucket"

        service = get_long_service_name("bitbucket")
        assert service == "bitbucket"

        service = get_short_service_name("bitbucket")
        assert service == "bb"

        service = get_short_service_name("bb")
        assert service == "bb"

    def test_gh(self):
        service = get_long_service_name("gh")
        assert service == "github"

        service = get_long_service_name("github")
        assert service == "github"

        service = get_short_service_name("github")
        assert service == "gh"

        service = get_short_service_name("gh")
        assert service == "gh"
