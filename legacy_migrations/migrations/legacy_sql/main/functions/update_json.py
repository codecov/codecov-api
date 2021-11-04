def run_sql(schema_editor):
    schema_editor.execute(
        """
        create or replace function add_key_to_json(jsonb, text, jsonb) returns jsonb as $$
        select case when $1 is null and $3 is null then ('{"'||$2||'":null}')::jsonb
                    when $1 is null or $1::text = '{}' then ('{"'||$2||'":'||$3||'}')::jsonb
                    when $3 is null then (left($1::text, -1)||',"'||$2||'":null}')::jsonb
                    else (left($1::text, -1)||',"'||$2||'":'||$3::text||'}')::jsonb end;
        $$ language sql stable;


        create or replace function add_key_to_json(jsonb, text, integer) returns jsonb as $$
        select case when $1 is null and $3 is null then ('{"'||$2||'":null}')::jsonb
                    when $1 is null or $1::text = '{}' then ('{"'||$2||'":'||$3||'}')::jsonb
                    when $3 is null then (left($1::text, -1)||',"'||$2||'":null}')::jsonb
                    else (left($1::text, -1)||',"'||$2||'":'||$3::text||'}')::jsonb end;
        $$ language sql stable;


        create or replace function add_key_to_json(jsonb, text, text) returns jsonb as $$
        select case when $1 is null and $3 is null then ('{"'||$2||'":null}')::jsonb
                    when $1 is null or $1::text = '{}' then ('{"'||$2||'":"'||$3||'"}')::jsonb
                    when $3 is null then (left($1::text, -1)||',"'||$2||'":null}')::jsonb
                    else (left($1::text, -1)||',"'||$2||'":"'||$3::text||'"}')::jsonb end;
        $$ language sql stable;


        create or replace function remove_key_from_json(jsonb, text) returns jsonb as $$
        with drop_key as (
            select key, value::text
            from jsonb_each($1::jsonb)
            where key != $2::text and value is not null
        ) select ('{'||array_to_string((select array_agg('"'||key||'":'||value) from drop_key), ',')||'}')::jsonb;
        $$ language sql stable;


        create or replace function update_json(jsonb, text, jsonb) returns jsonb as $$
        select case when $1 is not null then add_key_to_json(coalesce(remove_key_from_json($1, $2), '{}'::jsonb), $2, $3)
                    when $3 is null then ('{"'||$2||'":null}')::jsonb
                    else ('{"'||$2||'":'||coalesce($3::text, 'null')::text||'}')::jsonb end;
        $$ language sql stable;


        create or replace function update_json(jsonb, text, integer) returns jsonb as $$
        select case when $1 is not null then add_key_to_json(coalesce(remove_key_from_json($1, $2), '{}'::jsonb), $2, $3)
                    when $3 is null then ('{"'||$2||'":null}')::jsonb
                    else ('{"'||$2||'":'||$3::text||'}')::jsonb end;
        $$ language sql stable;


        create or replace function update_json(jsonb, text, text) returns jsonb as $$
        select case when $1 is not null then add_key_to_json(coalesce(remove_key_from_json($1, $2), '{}'::jsonb), $2, $3)
                    when $3 is null then ('{"'||$2||'":null}')::jsonb
                    else ('{"'||$2||'":"'||$3||'"}')::jsonb end;
        $$ language sql stable;
    """
    )
