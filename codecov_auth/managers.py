from django.db.models import Exists, F, Func, OuterRef, Q, QuerySet, Subquery

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
            activated=Exists(
                Owner.objects.filter(
                    ownerid=owner.ownerid,
                    plan_activated_users__contains=Func(
                        OuterRef("ownerid"),
                        function="ARRAY",
                        template="%(function)s[%(expressions)s]",
                    ),
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
                        OuterRef("ownerid"),
                        function="ARRAY",
                        template="%(function)s[%(expressions)s]",
                    ),
                )
            )
        )
