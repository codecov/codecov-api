from rest_framework.views import APIView
from django.http import HttpResponse
from rest_framework.permissions import AllowAny
from rest_framework import status
from rest_framework.response import Response
from .helpers.badge import get_badge, format_coverage_precision
from codecov_auth.models import Owner
from core.models import Repository, Branch
from internal_api.mixins import RepoPropertyMixin
from django.shortcuts import Http404

class BadgeHandler(APIView, RepoPropertyMixin):
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

        coverage = self.get_coverage()

        # Format coverage according to precision      
        coverage = format_coverage_precision(coverage, precision)
        
        if ext == 'txt':
            return HttpResponse(coverage)

        badge = get_badge(coverage, [70, 100], precision)
        return HttpResponse(badge)
    
    def get_coverage(self):
        """
            Note: This endpoint has the behaviour of returning a gray badge with the word 'unknwon' instead of returning a 404
                  when the user enters an invalid service, owner, repo or when coverage is not found for a branch. 

                  We also need to support service abbreviations for users already using them
        """
        self.kwargs["service"] = self.short_services[self.kwargs.get("service")] if self.kwargs.get("service") in self.short_services else self.kwargs.get("service")
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
        commit = repo.commits.filter(commitid=branch.head).first()

        flag = self.request.query_params.get('flag')
        if flag:
            return self.flag_coverage(flag, commit)

        return commit.totals.get('c') if commit is not None and commit.totals is not None else None

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
