import logging

from shared.reports.resources import Report
from shared.utils.sessions import Session

log = logging.getLogger(__name__)


def files_belonging_to_flags(commit_report: Report, flags: list[str]) -> list[str]:
    sessions_for_specific_flags = _sessions_with_specific_flags(
        commit_report=commit_report, flags=flags
    )
    session_ids = list(sessions_for_specific_flags.keys())
    files_in_specific_sessions = files_in_sessions(
        commit_report=commit_report, session_ids=session_ids
    )
    return files_in_specific_sessions


def _sessions_with_specific_flags(
    commit_report: Report, flags: list[str]
) -> dict[int, Session]:
    sessions = [
        (sid, session)
        for sid, session in commit_report.sessions.items()
        if session.flags and set(session.flags) & set(flags)
    ]
    return dict(sessions)


def files_in_sessions(commit_report: Report, session_ids: list[int]) -> list[str]:
    files, session_ids_set = [], set(session_ids)
    for file in commit_report:
        found = False
        for line in file:
            if line:
                for session in line.sessions:
                    if session.id in session_ids_set:
                        found = True
                        break
            if found:
                break
        if found:
            files.append(file.name)
    return files
