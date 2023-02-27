from django.db.models import Exists, Func, Manager, OuterRef, Q, QuerySet, Subquery
from django.db.models.functions import Coalesce

from core.models import Pull


class OwnerQuerySet(QuerySet):
    def users_of(self, owner):
        """
        Returns users of "owner", which is defined as Owner objects
        whose "organizations" field contains the "owner"s ownerid
        or is one of the "owner"s "plan_activated_users".
        """
        filters = Q(organizations__contains=[owner.ownerid])
        if owner.plan_activated_users:
            filters = filters | Q(ownerid__in=owner.plan_activated_users)

        return self.filter(filters)

    def annotate_activated_in(self, owner):
        """
        Annotates queryset with "activated" field, which is True
        if a given user is activated in organization "owner", false
        otherwise.
        """
        from codecov_auth.models import Owner

        return self.annotate(
            activated=Coalesce(
                Exists(
                    Owner.objects.filter(
                        ownerid=owner.ownerid,
                        plan_activated_users__contains=Func(
                            OuterRef("ownerid"),
                            function="ARRAY",
                            template="%(function)s[%(expressions)s]",
                        ),
                    )
                ),
                False,
            )
        )

    def annotate_is_admin_in(self, owner):
        """
        Annotates queryset with "is_admin" field, which is True
        if a given user is an admin in organization "owner", and
        false otherwise.
        """
        from codecov_auth.models import Owner

        return self.annotate(
            is_admin=Coalesce(
                Exists(
                    Owner.objects.filter(
                        ownerid=owner.ownerid,
                        admins__contains=Func(
                            OuterRef("ownerid"),
                            function="ARRAY",
                            template="%(function)s[%(expressions)s]",
                        ),
                    )
                ),
                False,
            )
        )

    def annotate_last_pull_timestamp(self):
        pulls = Pull.objects.filter(author=OuterRef("pk")).order_by("-updatestamp")
        return self.annotate(
            last_pull_timestamp=Subquery(pulls.values("updatestamp")[:1]),
        )


# We cannot use `QuerySet.as_manager()` since it relies on the `inspect` module and will
# not play nicely with Cython (which we use for self-hosted):
# https://cython.readthedocs.io/en/latest/src/userguide/limitations.html#inspect-support
class OwnerManager(Manager):
    def get_queryset(self):
        return OwnerQuerySet(self.model, using=self._db)

    def users_of(self, *args, **kwargs):
        return self.get_queryset().users_of(*args, **kwargs)
