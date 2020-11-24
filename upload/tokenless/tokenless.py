import os
import logging
import requests
from json import load
from rest_framework import status
from django.http import HttpResponse
from requests.exceptions import ConnectionError, HTTPError
from datetime import datetime, timedelta
from upload.tokenless.travis import TokenlessTravisHandler
from upload.tokenless.azure import TokenlessAzureHandler
from upload.tokenless.appveyor import TokenlessAppveyorHandler
from upload.tokenless.circleci import TokenlessCircleciHandler

log = logging.getLogger(__name__)

class TokenlessUploadHandler(object):

    ci_verifiers = {
        "appveyor": TokenlessAppveyorHandler,
        "azure_pipelines": TokenlessAzureHandler,
        "travis": TokenlessTravisHandler,
        "circleci": TokenlessCircleciHandler
    }

    def __init__(self, ci_type, upload_params):
        self.verifier = self.ci_verifiers.get(ci_type, None)
        self.upload_params = upload_params
        self.ci_type = ci_type

    def verify_upload(self):
        log.info(f"Started {self.ci_type} tokenless upload",
            extra=dict(
                commit=self.upload_params.get('commit'),
                repo_name=self.upload_params.get('repo'),
                job=self.upload_params.get('job'),
                owner=self.upload_params.get('owner')
            )
        )
        return self.verifier(self.upload_params).verify()
