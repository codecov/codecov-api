def run_sql(schema_editor):
    schema_editor.execute(
        """
        create or replace function array_append_unique(anyarray, anyelement) returns anyarray as $$
        select case when $2 is null
                then $1
                else array_remove($1, $2) || array[$2]
                end;
        $$ language sql immutable;
    """
    )
