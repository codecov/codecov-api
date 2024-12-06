import logging

import shared.reports.api_report_service as report_service
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from rest_framework import exceptions
from rest_framework.exceptions import NotFound
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from shared.metrics import Counter, inc_counter

from api.shared.mixins import RepoPropertyMixin
from core.models import Branch, Pull
from graphs.settings import settings

from .helpers.badge import format_coverage_precision, get_badge
from .helpers.graphs import icicle, sunburst, tree
from .mixins import GraphBadgeAPIMixin

log = logging.getLogger(__name__)

FLARE_USE_COUNTER = Counter(
    "graph_activity",
    "How are graphs and flare being used?",
    [
        "position",
    ],
)
FLARE_SUCCESS_COUNTER = Counter(
    "graph_success",
    "How often are graphs successfully generated?",
    [
        "graph_type",
    ],
)


class IgnoreClientContentNegotiation(DefaultContentNegotiation):
    def select_parser(self, request, parsers):
        """
        Select the first parser in the `.parser_classes` list.
        """
        return parsers[0]

    def select_renderer(self, request, renderers, format_suffix):
        """
        Select the first renderer in the `.renderer_classes` list.
        """
        try:
            return super().select_renderer(request, renderers, format_suffix)
        except exceptions.NotAcceptable:
            log.info(
                f"Recieved unsupported HTTP_ACCEPT header: {request.META.get('HTTP_ACCEPT')}"
            )
            return (renderers[0], renderers[0].media_type)


class BadgeHandler(APIView, RepoPropertyMixin, GraphBadgeAPIMixin):
    content_negotiation_class = IgnoreClientContentNegotiation

    permission_classes = [AllowAny]

    extensions = ["svg", "txt"]
    precisions = ["0", "1", "2"]
    filename = "badge"

    def get_object(self, request, *args, **kwargs):
        # Validate coverage precision
        precision = self.request.query_params.get("precision", "0")
        if precision not in self.precisions:
            raise NotFound("Coverage precision should be one of [ 0 || 1 || 2 ]")

        coverage, coverage_range = self.get_coverage()

        # Format coverage according to precision
        coverage = format_coverage_precision(coverage, precision)

        if self.kwargs.get("ext") == "txt":
            return coverage

        return get_badge(coverage, coverage_range, precision)

    def get_coverage(self):
        """
        Note: This endpoint has the behavior of returning a gray badge with the word 'unknown' instead of returning a 404
              when the user enters an invalid service, owner, repo or when coverage is not found for a branch.

              We also need to support service abbreviations for users already using them
        """
        coverage_range = [70, 100]

        try:
            repo = self.repo
        except Http404:
            log.warning("Repo not found", extra=dict(repo=self.kwargs.get("repo_name")))
            return None, coverage_range

        if repo.private and repo.image_token != self.request.query_params.get("token"):
            log.warning(
                "Token provided does not match repo's image token",
                extra=dict(repo=repo),
            )
            return None, coverage_range

        branch_name = self.kwargs.get("branch") or repo.branch
        branch = Branch.objects.filter(
            name=branch_name, repository_id=repo.repoid
        ).first()

        if branch is None:
            log.warning(
                "Branch not found", extra=dict(branch_name=branch_name, repo=repo)
            )
            return None, coverage_range
        try:
            commit = repo.commits.filter(commitid=branch.head).first()
        except ObjectDoesNotExist:
            # if commit does not exist return None coverage
            log.warning("Commit not found", extra=dict(commit=branch.head))
            return None, coverage_range

        if repo.yaml and repo.yaml.get("coverage", {}).get("range") is not None:
            coverage_range = repo.yaml.get("coverage", {}).get("range")

        flag = self.request.query_params.get("flag")
        if flag:
            return self.flag_coverage(flag, commit), coverage_range

        coverage = (
            commit.totals.get("c")
            if commit is not None and commit.totals is not None
            else None
        )

        return coverage, coverage_range

    def flag_coverage(self, flag_name, commit):
        """
        Looks into a commit's report sessions and returns the coverage for a particular flag

        Parameters
        flag_name (string): name of flag
        commit (obj): commit object containing report
        """
        if commit.full_report is None:
            log.warning(
                "Commit's report not found", extra=dict(commit=commit, flag=flag_name)
            )
            return None
        flags = commit.full_report.flags
        if flags is None:
            return None
        flag = flags.get(flag_name)
        if flag:
            return flag.totals.coverage
        return None


class GraphHandler(APIView, RepoPropertyMixin, GraphBadgeAPIMixin):
    permission_classes = [AllowAny]

    extensions = ["svg"]
    filename = "graph"

    def get_object(self, request, *args, **kwargs):
        options = dict()
        graph = self.kwargs.get("graph")

        # a flare graph has been requested
        inc_counter(FLARE_USE_COUNTER, labels=dict(position=0))
        log.info(
            msg="flare graph activity",
            extra=dict(position="start", graph_type=graph, kwargs=self.kwargs),
        )

        flare = self.get_flare()
        # flare success, will generate and return graph
        inc_counter(FLARE_USE_COUNTER, labels=dict(position=20))

        if graph == "tree":
            options["width"] = int(
                self.request.query_params.get(
                    "width", settings["sunburst"]["options"]["width"] or 100
                )
            )
            options["height"] = int(
                self.request.query_params.get(
                    "height", settings["sunburst"]["options"]["height"] or 100
                )
            )
            inc_counter(FLARE_SUCCESS_COUNTER, labels=dict(graph_type=graph))
            log.info(
                msg="flare graph activity",
                extra=dict(position="success", graph_type=graph, kwargs=self.kwargs),
            )
            return tree(flare, None, None, **options)
        elif graph == "icicle":
            options["width"] = int(
                self.request.query_params.get(
                    "width", settings["icicle"]["options"]["width"] or 100
                )
            )
            options["height"] = int(
                self.request.query_params.get(
                    "height", settings["icicle"]["options"]["height"] or 100
                )
            )
            inc_counter(FLARE_SUCCESS_COUNTER, labels=dict(graph_type=graph))
            log.info(
                msg="flare graph activity",
                extra=dict(position="success", graph_type=graph, kwargs=self.kwargs),
            )
            return icicle(flare, **options)
        elif graph == "sunburst":
            options["width"] = int(
                self.request.query_params.get(
                    "width", settings["sunburst"]["options"]["width"] or 100
                )
            )
            options["height"] = int(
                self.request.query_params.get(
                    "height", settings["sunburst"]["options"]["height"] or 100
                )
            )
            inc_counter(FLARE_SUCCESS_COUNTER, labels=dict(graph_type=graph))
            log.info(
                msg="flare graph activity",
                extra=dict(position="success", graph_type=graph, kwargs=self.kwargs),
            )
            return sunburst(flare, **options)

    def get_flare(self):
        pullid = self.kwargs.get("pullid")

        if not pullid:
            # pullid not in kwargs, try to generate flare from commit
            inc_counter(FLARE_USE_COUNTER, labels=dict(position=12))
            return self.get_commit_flare()
        else:
            # pullid was included in the request
            inc_counter(FLARE_USE_COUNTER, labels=dict(position=1))
            pull_flare = self.get_pull_flare(pullid)
            if pull_flare is None:
                # failed to get flare from pull OR commit - graph request failed
                inc_counter(FLARE_USE_COUNTER, labels=dict(position=15))
                raise NotFound(
                    "Not found. Note: private repositories require ?token arguments"
                )
            return pull_flare

    def get_commit_flare(self):
        commit = self.get_commit()

        if commit is None:
            # could not find a commit - graph request failed
            inc_counter(FLARE_USE_COUNTER, labels=dict(position=13))
            raise NotFound(
                "Not found. Note: private repositories require ?token arguments"
            )

        # will attempt to build a report from a commit
        inc_counter(FLARE_USE_COUNTER, labels=dict(position=10))
        report = report_service.build_report_from_commit(commit)

        if report is None:
            # report generation failed
            inc_counter(FLARE_USE_COUNTER, labels=dict(position=14))
            raise NotFound("Not found. Note: file for chunks not found in storage")

        # report successfully generated
        inc_counter(FLARE_USE_COUNTER, labels=dict(position=11))
        return report.flare(None, [70, 100])

    def get_pull_flare(self, pullid):
        try:
            repo = self.repo
            # repo was included
            inc_counter(FLARE_USE_COUNTER, labels=dict(position=2))
        except Http404:
            return None
        pull = Pull.objects.filter(pullid=pullid, repository_id=repo.repoid).first()
        if pull is not None:
            # pull found
            inc_counter(FLARE_USE_COUNTER, labels=dict(position=3))
            if pull._flare is not None or pull._flare_storage_path is not None:
                # pull has flare
                inc_counter(FLARE_USE_COUNTER, labels=dict(position=4))
                return pull.flare
        # pull not found or pull does not have flare, try to generate flare
        inc_counter(FLARE_USE_COUNTER, labels=dict(position=5))
        return self.get_commit_flare()

    def get_commit(self):
        try:
            repo = self.repo
            # repo included in request
            inc_counter(FLARE_USE_COUNTER, labels=dict(position=6))
        except Http404:
            return None
        if repo.private and repo.image_token != self.request.query_params.get("token"):
            # failed auth
            inc_counter(FLARE_USE_COUNTER, labels=dict(position=7))
            return None

        commitid = self.kwargs.get("commit")
        if commitid:
            # commitid included on request
            inc_counter(FLARE_USE_COUNTER, labels=dict(position=8))
            commit = repo.commits.filter(commitid=commitid).first()
        else:
            branch_name = self.kwargs.get("branch") or repo.branch
            branch = Branch.objects.filter(
                name=branch_name, repository_id=repo.repoid
            ).first()
            if branch is None:
                # failed to get a commit
                inc_counter(FLARE_USE_COUNTER, labels=dict(position=16))
                return None

            # found a commit by finding a branch
            inc_counter(FLARE_USE_COUNTER, labels=dict(position=9))
            commit = repo.commits.filter(commitid=branch.head).first()

        return commit
