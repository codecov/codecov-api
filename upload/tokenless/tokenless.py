import logging
import os
from datetime import datetime, timedelta
from json import load

import requests
from django.http import HttpResponse
from requests.exceptions import ConnectionError, HTTPError
from rest_framework import status
from rest_framework.exceptions import NotFound

from upload.tokenless.appveyor import TokenlessAppveyorHandler
from upload.tokenless.azure import TokenlessAzureHandler
from upload.tokenless.circleci import TokenlessCircleciHandler
from upload.tokenless.cirrus import TokenlessCirrusHandler
from upload.tokenless.github_actions import TokenlessGithubActionsHandler
from upload.tokenless.travis import TokenlessTravisHandler

log = logging.getLogger(__name__)


class TokenlessUploadHandler(object):

    ci_verifiers = {
        "appveyor": TokenlessAppveyorHandler,
        "azure_pipelines": TokenlessAzureHandler,
        "circleci": TokenlessCircleciHandler,
        "cirrus_ci": TokenlessCirrusHandler,
        "github_actions": TokenlessGithubActionsHandler,
        "travis": TokenlessTravisHandler,
    }

    def __init__(self, ci_type, upload_params):
        self.verifier = self.ci_verifiers.get(ci_type.replace("-", "_"), None)
        self.upload_params = upload_params
        self.ci_type = ci_type

    def verify_upload(self):
        log.info(
            f"Started {self.ci_type} tokenless upload",
            extra=dict(
                commit=self.upload_params.get("commit"),
                repo_name=self.upload_params.get("repo"),
                job=self.upload_params.get("job"),
                owner=self.upload_params.get("owner"),
            ),
        )
        try:
            return self.verifier(self.upload_params).verify()
        except TypeError as e:
            raise NotFound(
                "Your CI provider is not compatible with tokenless uploads, please upload using your repository token to resolve this."
            )
