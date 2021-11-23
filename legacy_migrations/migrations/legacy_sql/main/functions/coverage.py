def run_sql(schema_editor):
    schema_editor.execute(
        """
        create or replace function get_coverage(service, citext, citext, citext default null) returns jsonb as $$
        -- floor is temporary here
        with d as (
            select floor((c.totals->>'c')::numeric) as c,
                coalesce((r.yaml->'coverage'->'range')::jsonb,
                            (o.yaml->'coverage'->'range')::jsonb) as r,
                case when r.private then r.image_token else null end as t
            from repos r
            inner join owners o using (ownerid)
            left join branches b using (repoid)
            inner join commits c on b.repoid=c.repoid and c.commitid=b.head
            where o.service = $1
                and o.username = $2
                and r.name = $3
                and b.branch = coalesce($4, r.branch)
            limit 1
        ) select to_jsonb(d) from d;
        $$ language sql stable;
    """
    )
