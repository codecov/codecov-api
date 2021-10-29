def run_sql(schema_editor):
    schema_editor.execute(
        """
        create or replace function insert_commit(int, text, text, int) returns void as $$
            begin

                update commits
                set state='pending'
                where repoid = $1
                and commitid = $2;

                if not found then
                insert into commits (repoid, commitid, branch, pullid, merged, timestamp, state)
                values ($1, $2, $3, $4, case when $4 is not null then false else null end, now(), 'pending')
                on conflict (repoid, commitid) do update
                    set branch=$3, pullid=$4,
                        merged=(case when $4 is not null then false else null end),
                        state='pending';
                end if;

                update repos
                set active=true, deleted=false, updatestamp=now()
                where repoid = $1
                    and (active is not true or deleted is true);

            end;
        $$ language plpgsql volatile;
    """
    )
