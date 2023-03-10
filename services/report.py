from typing import Optional

from django.db.models import Prefetch
from django.utils.functional import cached_property
from shared.helpers.flag import Flag
from shared.reports.readonly import ReadOnlyReport as SharedReadOnlyReport
from shared.reports.resources import Report
from shared.reports.types import ReportFileSummary, ReportTotals
from shared.utils.sessions import Session, SessionType

from core.models import Commit
from reports.models import AbstractTotals, CommitReport, ReportDetails, ReportSession
from services.archive import ArchiveService


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


def build_report(chunks, files, sessions, totals, report_class=None):
    if report_class is None:
        report_class = SerializableReport
    return report_class.from_chunks(
        chunks=chunks, files=files, sessions=sessions, totals=totals
    )


def build_report_from_commit(commit: Commit, report_class=None):
    """
    Builds a `shared.reports.resources.Report` from a given commit.

    Chunks are fetched from archive storage and the rest of the data is sourced
    from various `reports_*` tables in the database.
    """

    commit_report = _fetch_commit_report(commit)
    if not commit_report:
        return None

    chunks = ArchiveService(commit.repository).read_chunks(commit.commitid)
    files = _build_files(commit_report.reportdetails)
    sessions = {}
    for upload in commit_report.sessions.all():
        session = _build_session(upload)
        sessions[upload.order_number] = session

    report_totals = _build_totals(commit_report.reportleveltotals)
    return build_report(
        chunks, files, sessions, report_totals, report_class=report_class
    )


def _fetch_commit_report(commit: Commit) -> Optional[CommitReport]:
    """
    Fetch a single `CommitReport` for the given commit.
    All the necessary report relations are prefetched.
    """
    return (
        commit.reports.prefetch_related(
            Prefetch(
                "sessions",
                queryset=ReportSession.objects.select_related("uploadleveltotals"),
            ),
            "sessions__flags",
        )
        .select_related("reportdetails", "reportleveltotals")
        .first()
    )


def _build_totals(totals: AbstractTotals) -> ReportTotals:
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


def _build_session(upload: ReportSession) -> Session:
    """
    Build a `shared.utils.sessions.Session` from a database `reports_upload` record.
    """
    upload_totals = _build_totals(upload.uploadleveltotals)
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


def _build_files(report_details: ReportDetails) -> dict[str, ReportFileSummary]:
    """
    Construct a files dictionary in a format compatible with `shared.reports.resources.Report`
    from data in the `reports_reportdetails.files_array` column in the database.
    """

    return {
        file["filename"]: ReportFileSummary(
            file_index=file["file_index"],
            file_totals=ReportTotals(*file["file_totals"]),
            session_totals=[
                ReportTotals(*session) for session in file["session_totals"]
            ],
            diff_totals=file["diff_totals"],
        )
        for file in report_details.files_array
    }
