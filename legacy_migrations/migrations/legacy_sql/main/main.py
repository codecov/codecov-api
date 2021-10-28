from .functions.main import run_sql as functions_run_sql
from .tables.main import run_sql as tables_run_sql
from .triggers.main import run_sql as triggers_run_sql
from .types import run_sql as types_run_sql


def run_sql(schema_editor):
    schema_editor.execute(
        """
        create extension if not exists "uuid-ossp";
        create extension if not exists "citext";

        create table if not exists version (version text);

        create or replace function random_string(int) returns char as $$
            select string_agg(((string_to_array('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890', null))[floor(random()*62)+1])::text, '')
            from generate_series(1, $1);
        $$ language sql;
    """
    )
    types_run_sql(schema_editor)
    tables_run_sql(schema_editor)
    functions_run_sql(schema_editor)
    triggers_run_sql(schema_editor)
