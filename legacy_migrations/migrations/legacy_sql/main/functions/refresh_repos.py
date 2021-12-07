def run_sql(schema_editor):
    schema_editor.execute(
        """
        create or replace function refresh_teams(service, jsonb) returns int[] as $$
        declare ownerids int[];
        declare _ownerid int;
        declare _team record;
        begin
            for _team in select d from jsonb_array_elements($2) d loop
            update owners o
            set username = (_team.d->>'username')::citext,
                name = (_team.d->>'name')::text,
                email = (_team.d->>'email')::text,
                avatar_url = (_team.d->>'avatar_url')::text,
                parent_service_id = (_team.d->>'parent_id')::text,
                updatestamp = now()
            where service = $1
                and service_id = (_team.d->>'id')::text
            returning ownerid into _ownerid;

            if not found then
                insert into owners (service, service_id, username, name, email, avatar_url, parent_service_id)
                values ($1, 
                        (_team.d->>'id')::text, 
                        (_team.d->>'username')::citext, 
                        (_team.d->>'name')::text, 
                        (_team.d->>'email')::text, 
                        (_team.d->>'avatar_url')::text, 
                        (_team.d->>'parent_id')::text
                )
                returning ownerid into _ownerid;
            end if;

            select array_append(ownerids, _ownerid) into ownerids;

            end loop;

            return ownerids;

        end;
        $$ language plpgsql volatile strict;


        create or replace function refresh_repos(service, jsonb, int, boolean) returns text[] as $$
        declare _ text;
        declare _branch text;
        declare _forkid int;
        declare _previous_ownerid int;
        declare _ownerid int;
        declare _repo record;
        declare _repoid int;
        declare _bot int;
        declare repos text[];
        begin

            for _repo in select d from jsonb_array_elements($2) d loop

            select r.ownerid into _previous_ownerid
                from repos r
                inner join owners o using (ownerid)
                where o.service = $1
                and r.service_id = (_repo.d->'repo'->>'service_id')::text
                limit 1;

            -- owner
            -- =====
            -- its import to check all three below. otherwise update the record.
            select ownerid, bot, (yaml->'codecov'->>'branch')::text
                into _ownerid, _bot, _branch
                from owners
                where service = $1
                and service_id = (_repo.d->'owner'->>'service_id')::text
                and username = (_repo.d->'owner'->>'username')::citext
                limit 1;

            if not found then
                update owners
                set username = (_repo.d->'owner'->>'username')::citext,
                    updatestamp = now()
                where service = $1
                and service_id = (_repo.d->'owner'->>'service_id')::text
                returning ownerid, bot, (yaml->'codecov'->>'branch')::text
                into _ownerid, _bot, _branch;

                if not found then
                insert into owners (service, service_id, username, bot)
                values ($1, (_repo.d->'owner'->>'service_id')::text, (_repo.d->'owner'->>'username')::citext, $3)
                returning ownerid, bot into _ownerid, _bot;
                end if;

            end if;

            -- fork
            -- ====
            if (_repo.d->'repo'->>'fork') is not null then
                -- converts fork into array
                select refresh_repos($1, (select jsonb_agg(d.d::jsonb)::jsonb
                                        from (select (_repo.d->'repo'->>'fork')::jsonb d limit 1) d
                                        limit 1), null, null)
                into _
                limit 1;

                -- get owner
                select r.repoid into _forkid
                from repos r
                inner join owners o using (ownerid)
                where o.service = $1
                and o.username = (_repo.d->'repo'->'fork'->'owner'->>'username')::citext
                and r.name = (_repo.d->'repo'->'fork'->'repo'->>'name')::citext
                limit 1;
            else
                _forkid := null;
            end if;

            -- update repo
            -- ===========
            if _previous_ownerid is not null then
                -- repo already existed with this service_id, update it
                update repos set
                    private = ((_repo.d)->'repo'->>'private')::boolean,
                    forkid = _forkid,
                    language = ((_repo.d)->'repo'->>'language')::languages,
                    ownerid = _ownerid,
                    using_integration=(using_integration or $4),
                    name = (_repo.d->'repo'->>'name')::citext,
                    deleted = false,
                    updatestamp=now()
                where ownerid = _previous_ownerid
                    and service_id = (_repo.d->'repo'->>'service_id')::text
                returning repoid
                into _repoid;

            -- new repo
            -- ========
            else
                insert into repos (service_id, ownerid, private, forkid, name, branch, language, using_integration)
                values ((_repo.d->'repo'->>'service_id')::text,
                        _ownerid,
                        (_repo.d->'repo'->>'private')::boolean,
                        _forkid,
                        (_repo.d->'repo'->>'name')::citext,
                        coalesce(_branch, (_repo.d->'repo'->>'branch')),
                        (_repo.d->'repo'->>'language')::languages,
                        $4)
                returning repoid into _repoid;

            end if;

            -- return private repoids
            if (_repo.d->'repo'->>'private')::boolean then
                repos = array_append(repos, _repoid::text);
            end if;

            end loop;

            return repos;
        end;
        $$ language plpgsql volatile;
    """
    )
