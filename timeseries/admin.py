from datetime import datetime

import django.forms as forms
from django.conf import settings
from django.contrib import admin, messages
from django.db import transaction
from django.db.models import QuerySet
from django.shortcuts import render

from codecov.admin import AdminMixin
from core.models import Repository
from services.task import TaskService
from timeseries.models import Dataset


def enqueue_tasks(datasets: QuerySet, start_date: datetime, end_date: datetime):
    count = datasets.update(backfilled=False)

    for dataset in datasets:
        repository = Repository.objects.filter(pk=dataset.repository_id).first()
        if repository:
            TaskService().backfill_repo(
                repository,
                start_date=start_date,
                end_date=end_date,
                dataset_names=[dataset.name],
            )

    return count


class BackfillForm(forms.Form):
    start_date = forms.DateTimeField(required=True)
    end_date = forms.DateTimeField(required=True)


class DatasetAdmin(AdminMixin, admin.ModelAdmin):
    list_display = ("name", "repository", "backfilled")
    actions = ["backfill"]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        # this prevents an N+1 query from the `repository` method below
        repo_ids = list(queryset.values_list("repository_id", flat=True))
        self._repositories = {
            repository.pk: repository
            for repository in Repository.objects.filter(pk__in=repo_ids)
        }

        return queryset

    def repository(self, dataset):
        return self._repositories[dataset.repository_id]

    def backfill(self, request, queryset):
        if "backfill" in request.POST:
            form = BackfillForm(request.POST)
            if form.is_valid():
                count = enqueue_tasks(
                    queryset,
                    start_date=form.cleaned_data["start_date"],
                    end_date=form.cleaned_data["end_date"],
                )
                messages.success(
                    request, f"Enqueued backfill tasks for {count} datasets"
                )
                return
        else:
            form = BackfillForm()

        return render(
            request,
            "admin/backfill.html",
            context={
                "form": form,
                "datasets": queryset,
            },
        )


if settings.TIMESERIES_ENABLED:
    admin.site.register(Dataset, DatasetAdmin)
