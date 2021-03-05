from django.db.models import OuterRef, Exists, Func, QuerySet, F, Subquery, OuterRef
from core.models import Pull


class OwnerQuerySet(QuerySet):
    def users_of(self, owner):
        """
        Returns users of "owner", which is defined as Owner objects
        whose "organizations" field contains the "owner"s ownerid.
        """
        return self.filter(
            organizations__contains=[owner.ownerid]
        )

    def annotate_activated_in(self, owner):
        """
        Annotates queryset with "activated" field, which is True
        if a given user is activated in organization "owner", false
        otherwise.
        """
        from codecov_auth.models import Owner
        return self.annotate(
            activated=Exists(
                Owner.objects.filter(
                    ownerid=owner.ownerid,
                    plan_activated_users__contains=Func(
                        OuterRef('ownerid'),
                        function='ARRAY',
                        template="%(function)s[%(expressions)s]"
                    )
                )
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
            is_admin=Exists(
                Owner.objects.filter(
                    ownerid=owner.ownerid,
                    admins__contains=Func(
                        OuterRef('ownerid'),
                        function='ARRAY',
                        template="%(function)s[%(expressions)s]"
                    )
                )
            )
        )

    def annotate_with_latest_private_pr_date_in(self, owner):
        """
        Annotates queryset with date of most recent PR made to a pull
        request owned by "owner".
        """
        return self.annotate(
            latest_private_pr_date=Subquery(
                Pull.objects.exclude(updatestamp=None).filter(
                    author__ownerid=OuterRef("ownerid"),
                    repository__private=True,
                    repository__author__ownerid=owner.ownerid
                ).order_by("-updatestamp").values("updatestamp")[:1]
            )
        )

    def annotate_with_lastseen(self):
        """
        Annotates queryset with related Session.lastseen value.
        """
        from codecov_auth.models import Session
        return self.annotate(
            lastseen=Subquery(
                Session.objects.filter(
                    owner__ownerid=OuterRef("ownerid")
                ).order_by("-lastseen").values("lastseen")[:1]
            )
        )
