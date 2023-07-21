import pytest

from utils.config import should_write_data_to_storage_config_check


@pytest.mark.parametrize(
    "inner_config, func_args, result",
    [
        (
            {
                "repo_ids": [],
                "only_codecov": True,
                "report_details_files_array": True,
                "commit_report": False,
            },
            ("report_details_files_array", False, 1),
            False,
        ),
        (
            {
                "repo_ids": [],
                "only_codecov": True,
                "report_details_files_array": True,
                "commit_report": False,
            },
            ("report_details_files_array", True, 1),
            True,
        ),
        (
            {
                "repo_ids": [],
                "only_codecov": True,
                "report_details_files_array": True,
                "commit_report": False,
            },
            ("commit_report", True, 1),
            False,
        ),
        (
            {
                "repo_ids": [1],
                "only_codecov": True,
                "report_details_files_array": True,
                "commit_report": False,
            },
            ("commit_report", False, 1),
            False,
        ),
        (
            {
                "repo_ids": [1],
                "only_codecov": True,
                "report_details_files_array": True,
                "commit_report": False,
            },
            ("report_details_files_array", False, 1),
            True,
        ),
    ],
)
def test_should_write_data_to_storage_config_check(
    inner_config, func_args, result, mocker
):
    config = {"setup": {"save_report_data_in_storage": inner_config}}

    def fake_config(*path, default=None):
        curr = config
        for key in path:
            if key in curr:
                curr = curr.get(key)
            else:
                return default
        return curr

    mocker.patch("utils.config.get_config", side_effect=fake_config)
    assert should_write_data_to_storage_config_check(*func_args) == result
