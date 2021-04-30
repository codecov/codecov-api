from django.db import models

import sys

is_testing = "pytest" in sys.modules


class EnvVarsExposed(models.Model):
    owner_id = models.IntegerField(blank=True, null=True)
    repo_id = models.IntegerField(blank=True, null=True)
    is_repo_private = models.BooleanField(blank=True, null=True)
    severity_from_log_analysis = models.CharField(max_length=50, blank=True, null=True)
    exists_on_codecov = models.BooleanField(blank=True, null=True)
    known_clone_by_attacker = models.BooleanField(blank=True, null=True)
    exposed_env_vars = models.TextField(blank=True, null=True)
    sensitive_exposed_in_git_origin = models.TextField(blank=True, null=True)

    class Meta:
        managed = not is_testing
        db_table = "env_vars_exposed"
        unique_together = (("owner_id", "repo_id"),)

    def generate_message(self):
        secondary_message = None
        key_list = None
        if self.known_clone_by_attacker:
            secondary_message = "We have reason to believe that this repo may have been downloaded by the threat actor. We recommend reaching out to your git provider for more information."
        elif self.exposed_env_vars:
            secondary_message = "We have reason to believe the following environment variables were affected."
            key_list = self.exposed_env_vars.split(",")
        elif self.sensitive_exposed_in_git_origin:
            secondary_message = "We have reason to believe the following sensitive keys were exposed. For security and privacy reasons, we’ve limited the keys to the first seven characters to help you identify the key, without printing it in full."
            key_list = self.sensitive_exposed_in_git_origin.split(",")

        return {
            "header": "Additional Information: This repo was impacted by Codecov’s Bash Uploader Incident",
            "message": "We have additional information about this repo. This information should not be considered exhaustive, but may help you in the investigation of compromised tokens.",
            "secondary_message": secondary_message,
            "key_list": key_list,
        }
