from loguru import logger
from typing import List, Optional

import sentry_sdk
from django.conf import settings
from django.db.models import Prefetch, Q
from django.utils.functional import cached_property
from shared.helpers.flag import Flag
from shared.reports.readonly import ReadOnlyReport as SharedReadOnlyReport
from shared.reports.resources import Report
from shared.reports.types import ReportFileSummary, ReportTotals
from shared.storage.exceptions import FileNotInStorageError
from shared.utils.sessions import Session, SessionType

from core.models import Commit
from reports.models import AbstractTotals, CommitReport, ReportDetails, ReportSession
from services.archive import ArchiveService
from utils.config import RUN_ENV


class ReportMixin:
    def file_reports(self):
        for f in self.files:
            yield self.get(f)

    @cached_property
    def flags(self):
        """returns dict(:name=<Flag>)"""
        flags_dict = {}
        for sid, session in self.sessions.items():
            if session.flags is not None:
                carriedforward = session.session_type.value == "carriedforward"
                carriedforward_from = session.session_extras.get("carriedforward_from")
                for flag in session.flags:
                    flags_dict[flag] = Flag(
                        self,
                        flag,
                        carriedforward=carriedforward,
                        carriedforward_from=carriedforward_from,
                    )
        return flags_dict


class SerializableReport(ReportMixin, Report):
    pass


class ReadOnlyReport(ReportMixin, SharedReadOnlyReport):
    pass


@sentry_sdk.trace
def build_report(chunks, files, sessions, totals, report_class=None):
    if report_class is None:
        report_class = SerializableReport
    return report_class.from_chunks(
        chunks=chunks, files=files, sessions=sessions, totals=totals
    )


@sentry_sdk.trace
def build_report_from_commit(commit: Commit, report_class=None):
    """
    Builds a `shared.reports.resources.Report` from a given commit.

    Chunks are fetched from archive storage and the rest of the data is sourced
    from various `reports_*` tables in the database.
    """

    # TODO: this can be removed once confirmed working well on prod
    new_report_builder_enabled = (
        RUN_ENV == "DEV"
        or RUN_ENV == "STAGING"
        or RUN_ENV == "TESTING"
        or commit.repository_id in settings.REPORT_BUILDER_REPO_IDS
    )

    with sentry_sdk.start_span(description="Fetch files/sessions/totals"):
        commit_report = fetch_commit_report(commit)
        if commit_report and new_report_builder_enabled:
            files = build_files(commit_report)
            sessions = build_sessions(commit_report)
            try:
                totals = build_totals(commit_report.reportleveltotals)
            except CommitReport.reportleveltotals.RelatedObjectDoesNotExist:
                totals = None
        else:
            if not commit.report:
                return None

            files = commit.report["files"]
            sessions = commit.report["sessions"]
            totals = commit.totals

    try:
        with sentry_sdk.start_span(description="Fetch chunks"):
            chunks = ArchiveService(commit.repository).read_chunks(commit.commitid)
        return build_report(chunks, files, sessions, totals, report_class=report_class)
    except FileNotInStorageError:
        logger.warning(
            "File for chunks not found in storage",
            extra=dict(
                commit=commit.commitid,
                repo=commit.repository_id,
            ),
        )
        return None


def fetch_commit_report(commit: Commit) -> Optional[CommitReport]:
    """
    Fetch a single `CommitReport` for the given commit.
    All the necessary report relations are prefetched.
    """
    return (
        commit.reports.coverage_reports()
        .filter(code=None)
        .prefetch_related(
            Prefetch(
                "sessions",
                queryset=ReportSession.objects.prefetch_related("flags").select_related(
                    "uploadleveltotals"
                ),
            ),
        )
        .select_related("reportdetails", "reportleveltotals")
        .first()
    )


def build_totals(totals: AbstractTotals) -> ReportTotals:
    """
    Build a `shared.reports.types.ReportTotals` instance from one of the
    various database totals records.
    """
    return ReportTotals(
        files=totals.files,
        lines=totals.lines,
        hits=totals.hits,
        misses=totals.misses,
        partials=totals.partials,
        coverage=totals.coverage,
        branches=totals.branches,
        methods=totals.methods,
    )


def build_session(upload: ReportSession) -> Session:
    """
    Build a `shared.utils.sessions.Session` from a database `reports_upload` record.
    """
    try:
        upload_totals = build_totals(upload.uploadleveltotals)
    except ReportSession.uploadleveltotals.RelatedObjectDoesNotExist:
        # upload does not have any totals - maybe the processing failed
        # or the upload was empty?
        upload_totals = None
    flags = [flag.flag_name for flag in upload.flags.all()]

    return Session(
        id=upload.id,
        totals=upload_totals,
        time=upload.created_at.timestamp,
        archive=upload.storage_path,
        flags=flags,
        provider=upload.provider,
        build=upload.build_code,
        job=upload.job_code,
        url=upload.build_url,
        state=upload.state,
        env=upload.env,
        name=upload.name,
        session_type=SessionType.get_from_string(upload.upload_type),
        session_extras=upload.upload_extras,
    )


def build_sessions(commit_report: CommitReport) -> dict[int, Session]:
    """
    Build mapping of report number -> session that can be passed to the report class.
    Does not include CF sessions if there is also an upload session with the same
    flag name.
    """
    sessions = {}

    carryforward_sessions = {}
    uploaded_flags = set()

    for upload in commit_report.sessions.filter(
        Q(state="complete") | Q(state="processed")
    ):
        session = build_session(upload)
        if session.session_type == SessionType.carriedforward:
            carryforward_sessions[upload.order_number] = session
        else:
            sessions[upload.order_number] = session
            uploaded_flags |= set(session.flags)

    for sid, session in carryforward_sessions.items():
        # we only ever expect 1 flag for CF sessions
        overlapping_flags = uploaded_flags & set(session.flags)

        if len(overlapping_flags) == 0:
            # we can include this CF session since there are no direct uploads
            # with the same flag name
            sessions[sid] = session

    return sessions


def build_files(commit_report: CommitReport) -> dict[str, ReportFileSummary]:
    """
    Construct a files dictionary in a format compatible with `shared.reports.resources.Report`
    from data in the `reports_reportdetails.files_array` column in the database.
    """
    try:
        report_details = commit_report.reportdetails
    except CommitReport.reportdetails.RelatedObjectDoesNotExist:
        # we don't expect this but something could have gone wrong in the worker
        # we can't really recover here
        return {}

    return {
        file["filename"]: ReportFileSummary(
            file_index=file["file_index"],
            file_totals=ReportTotals(*file["file_totals"]),
            session_totals=file["session_totals"],
            diff_totals=file["diff_totals"],
        )
        for file in report_details.files_array
    }


def files_belonging_to_flags(commit_report: Report, flags: List[str]) -> List[str]:
    sessions_for_specific_flags = sessions_with_specific_flags(
        commit_report=commit_report, flags=flags
    )
    session_ids = list(sessions_for_specific_flags.keys())
    files_in_specific_sessions = files_in_sessions(
        commit_report=commit_report, session_ids=session_ids
    )
    return files_in_specific_sessions


def sessions_with_specific_flags(
    commit_report: Report, flags: List[str]
) -> dict[int, Session]:
    sessions = [
        (sid, session)
        for sid, session in commit_report.sessions.items()
        if session.flags and set(session.flags) & set(flags)
    ]
    return dict(sessions)


def files_in_sessions(commit_report: Report, session_ids: List[int]) -> List[str]:
    files, session_ids = [], set(session_ids)
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
