import logging

from django.db.backends.postgresql.base import DatabaseWrapper as PostgresWrapper
from django.db.models import Field, Lookup

log = logging.getLogger(__name__)


class DatabaseWrapper(PostgresWrapper):
    def _cursor(self, *args, **kwargs):
        """
        Check to make sure a connection is usable.
        If it's not then we close the connection so that it will automatically reconnect
        in the call to `super._cursor`.
        """
        if self.connection:
            if not self.is_usable():
                log.warning("closing unusable database connection")
                self.connection.close()
                self.connection = None
        return super(DatabaseWrapper, self)._cursor(*args, **kwargs)


@Field.register_lookup
class IsNot(Lookup):
    lookup_name = "isnot"

    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        params = lhs_params + rhs_params
        return "%s is not %s" % (lhs, rhs), params
