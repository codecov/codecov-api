from django.db.backends.postgresql.base import DatabaseWrapper as PostgresWrapper


class DatabaseWrapper(PostgresWrapper):
    def _cursor(self, *args, **kwargs):
        """
        Check to make sure a connection is usable.
        If it's not then we close the connection so that it will automatically reconnect
        in the call to `super._cursor`.
        """
        if self.connection:
            if not self.is_usable():
                self.connection.close()
                self.connection = None
        return super(DatabaseWrapper, self)._cursor(*args, **kwargs)
