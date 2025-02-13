from shared.reports.resources import Report


def files_belonging_to_flags(commit_report: Report, flags: list[str]) -> list[str]:
    flags_set = set(flags)
    session_ids = {
        sid
        for sid, session in commit_report.sessions.items()
        if session.flags and not set(session.flags).isdisjoint(flags_set)
    }
    files_in_specific_sessions = files_in_sessions(
        commit_report=commit_report, session_ids=session_ids
    )
    return files_in_specific_sessions


def files_in_sessions(commit_report: Report, session_ids: set[int]) -> list[str]:
    files = []
    for file in commit_report:
        found = False
        for line in file:
            if line:
                for session in line.sessions:
                    if session.id in session_ids:
                        found = True
                        break
            if found:
                break
        if found:
            files.append(file.name)
    return files
