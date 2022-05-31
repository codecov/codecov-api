def repo_commits(request, repo: str):
    raise NotImplementedError([repo])


def repo_commits_reports(request, repo: str, commit_id: str):
    raise NotImplementedError([repo, commit_id])


def repo_commits_reports_uploads(request, repo: str, commit_id: str, report_id: str):
    raise NotImplementedError([repo, commit_id, report_id])
