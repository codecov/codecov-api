def run_sql(schema_editor):
    schema_editor.execute(
        """
        drop function if exists _pop_first_as_json(jsonb[]) cascade;
        drop function if exists _max_coverage(jsonb[]) cascade;
        drop function if exists _min_coverage(jsonb[]) cascade;

        create or replace function _pop_first_as_json(jsonb[]) returns jsonb as $$
        select $1[1]::jsonb;
        $$ language sql immutable;


        create or replace function _max_coverage(jsonb[], jsonb) returns jsonb[] as $$
        select case when $1 is null then array[$2]
                    when ($1[1]->>'c')::numeric > ($2->>'c')::numeric then $1
                    else array[$2] end;
        $$ language sql immutable;


        create aggregate max_coverage(jsonb) (
            SFUNC = _max_coverage,
            STYPE = jsonb[],
            FINALFUNC = _pop_first_as_json
        );


        create or replace function _min_coverage(jsonb[], jsonb) returns jsonb[] as $$
        select case when $1 is null then array[$2]
                    when ($1[1]->>'c')::numeric < ($2->>'c')::numeric then $1
                    else array[$2] end;
        $$ language sql immutable;


        create aggregate min_coverage(jsonb) (
        SFUNC = _min_coverage,
        STYPE = jsonb[],
        FINALFUNC = _pop_first_as_json
        );


        create or replace function ratio(int, int) returns text as $$
        select case when $2 = 0 then '0' else round(($1::numeric/$2::numeric)*100.0, 5)::text end;
        $$ language sql immutable;


        create or replace function _agg_report_totals(text[], jsonb) returns text[] as $$
        -- fnhmpcbdMs
        select case when $1 is null
                then array[$2->>0, $2->>1, $2->>2, $2->>3,
                            $2->>4, $2->>5, $2->>6, $2->>7,
                            $2->>8, $2->>9]
                else array[($1[1]::int + ($2->>0)::int)::text,
                            ($1[2]::int + ($2->>1)::int)::text,
                            ($1[3]::int + ($2->>2)::int)::text,
                            ($1[4]::int + ($2->>3)::int)::text,
                            ($1[5]::int + ($2->>4)::int)::text,
                            ratio(($1[3]::int + ($2->>2)::int), ($1[2]::int + ($2->>1)::int)),
                            ($1[7]::int + ($2->>6)::int)::text,
                            ($1[8]::int + ($2->>7)::int)::text,
                            ($1[9]::int + ($2->>8)::int)::text,
                            ($1[10]::int + ($2->>9)::int)::text] end;
        $$ language sql immutable;


        create aggregate agg_totals(jsonb) (
        SFUNC = _agg_report_totals,
        STYPE = text[]
        );
    
    """
    )
