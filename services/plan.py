import enum
from datetime import timedelta

from django.forms import ValidationError
from django.utils import timezone
from django.utils.functional import cached_property

from codecov_auth.models import Owner


class TrialStatusChoices(enum.Enum):
    NOT_STARTED = "not_started"
    ONGOING = "ongoing"
    EXPIRED = "expired"


TRIAL_DAYS_LENGTH = 14


class PlanService(object):
    def __init__(self, current_org: Owner):
        """
        Method that determines the trial status based on the trial_start_date and
        the trial_end_date.

        Args:
            current_org (Owner): this is selected organization entry. This is not the user that is sending the request.

        Returns:
            No value
        """
        self.current_org = current_org
        self.plan_name = current_org.plan

    @cached_property
    def trial_status(self) -> None:
        """
        Method that determines the trial status based on the trial_start_date and
        the trial_end_date.

        Returns:
            No value
        """
        if self.current_org.trial_start_date is None:
            return TrialStatusChoices.NOT_STARTED
        if timezone.now() > self.current_org.trial_end_date:
            return TrialStatusChoices.EXPIRED
        else:
            return TrialStatusChoices.ONGOING

    def start_trial(self) -> None:
        """
        Method that starts trial on an organization if the trial_start_date
        is not empty.

        Returns:
            No value

        Raises:
            ValidationError: if trial has already started
        """
        if self.trial_status != TrialStatusChoices.NOT_STARTED:
            raise ValidationError("Cannot start an existing trial")
        start_date = timezone.now()
        self.current_org.trial_start_date = start_date
        self.current_org.trial_end_date = start_date + timedelta(days=TRIAL_DAYS_LENGTH)
        self.current_org.save()

    def expire_trial_preemptively(self) -> None:
        """
        Method that expires a trial upon demand. Usually trials will be considered
        expired based on the 'trial_status' property above, but a user can decide to
        cause that expiration premptively

        Returns:
            No value
        """
        # I initially wanted to raise a validation error if there wasnt a start date/end date, but this will
        # be hard to apply for entries before this migration without start/end trial dates
        self.current_org.trial_end_date = timezone.now()
        self.current_org.save()
