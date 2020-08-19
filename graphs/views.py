import json
from rest_framework.views import APIView
from django.http import HttpResponse
from rest_framework.permissions import AllowAny
from rest_framework import status, exceptions
from rest_framework.response import Response
from .helpers.badge import get_badge, format_coverage_precision
from codecov_auth.models import Owner
from core.models import Repository, Branch
from internal_api.mixins import RepoPropertyMixin
from django.shortcuts import Http404
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.negotiation import DefaultContentNegotiation
from services.redis import get_redis_connection

redis = get_redis_connection()

import logging

log = logging.getLogger(__name__)


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

class BadgeHandler(APIView, RepoPropertyMixin):

    content_negotiation_class = IgnoreClientContentNegotiation

    permission_classes = [AllowAny]

    extensions = ['svg', 'txt']
    precisions = ['0', '1', '2']
    short_services = {
        'gh': 'github',
        'bb': 'bitbucket',
        'gl': 'gitlab'
    }

    def get(self, request, *args, **kwargs):
        # Validate file extensions
        ext = self.kwargs.get('ext')
        if not ext in self.extensions:
            return Response({"detail": "File extension should be one of [ .svg || .txt ]"}, status=status.HTTP_404_NOT_FOUND)
        
        # Validate coverage precision
        precision = self.request.query_params.get('precision', '0')
        if not precision in self.precisions:
            return Response({"detail": "Coverage precision should be one of [ 0 || 1 || 2 ]"}, status=status.HTTP_404_NOT_FOUND)

        self.kwargs["service"] = self.short_services[self.kwargs.get("service")] if self.kwargs.get("service") in self.short_services else self.kwargs.get("service")

        coverage = self.get_coverage()

        # Format coverage according to precision      
        coverage = format_coverage_precision(coverage, precision)
        
        if ext == 'txt':
            return HttpResponse(coverage)

        badge = get_badge(coverage, [70, 100], precision)
        response = HttpResponse(badge)
        response['Content-Disposition'] =' inline; filename="badge.svg"'
        response['Content-Type'] = 'image/svg+xml'
        return response
    
    def get_coverage(self):
        """
            Note: This endpoint has the behaviour of returning a gray badge with the word 'unknwon' instead of returning a 404
                  when the user enters an invalid service, owner, repo or when coverage is not found for a branch. 

                  We also need to support service abbreviations for users already using them
        """
        coverage = self.get_cached_coverage()
        if coverage is not None:
            return coverage
        try:
            repo = self.repo
        except Http404:
            return None

        if repo.private and repo.image_token != self.request.query_params.get('token'):
            return None
       
        branch_name = self.kwargs.get('branch') or repo.branch
        branch = Branch.objects.filter(name=branch_name, repository_id=repo.repoid).first()
       
        if branch is None:
            return None
        try:
            commit = repo.commits.get(commitid=branch.head)
        except ObjectDoesNotExist:
            # if commit does not exist return None coverage
            return None
            

        flag = self.request.query_params.get('flag')
        if flag:
            return self.flag_coverage(flag, commit)

        coverage = commit.totals.get('c') if commit is not None and commit.totals is not None else None

        if coverage is not None and flag is None:
            coverage_key = ':'.join((self.kwargs["service"], self.kwargs.get("owner_username"), self.kwargs.get("repo_name"), self.kwargs.get('branch') or '')).lower()
            redis.hset('badge', coverage_key, json.dumps({'r': None, 'c': coverage, 't': repo.image_token if repo.private else None }))

        return coverage

    def flag_coverage(self, flag, commit):
        """
        Looks into a commit's report sessions and returns the coverage for a perticular flag
        
        Parameters
        flag (string): name of flag
        commit (obj): commit object containing report
        """
        sessions = commit.report.get('sessions')
        for key, data in sessions.items():
            if flag in data.get('f', []):
                totals = data.get('t', [])
                return totals[5] if len(totals) > 5 else None
        return None


    def get_cached_coverage(self):
        coverage_key = ':'.join((self.kwargs["service"], self.kwargs.get("owner_username"), self.kwargs.get("repo_name"), self.kwargs.get('branch') or '')).lower()
        coverage = redis.hget('badge', coverage_key)
        if coverage:
            coverage = json.loads(coverage)
            if coverage is None:
                return None
            token = coverage.get('t')
            if token and token != self.request.query_params.get('token'):
                return None
            return coverage['c']
        else:
            return None
