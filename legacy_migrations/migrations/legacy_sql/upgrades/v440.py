from ..main.functions.aggregates import run_sql as aggregates_run_sql
from ..main.functions.coverage import run_sql as coverage_run_sql
from ..main.functions.get_access_token import run_sql as get_access_token_run_sql
from ..main.functions.get_author import run_sql as get_author_run_sql
from ..main.functions.get_commit import run_sql as get_commit_run_sql
from ..main.functions.get_customer import run_sql as get_customer_run_sql
from ..main.functions.get_graph_for import run_sql as get_graph_for_run_sql
from ..main.functions.get_ownerid import run_sql as get_ownerid_run_sql
from ..main.functions.get_repo import run_sql as get_repo_run_sql
from ..main.functions.get_user import run_sql as get_user_run_sql
from ..main.functions.insert_commit import run_sql as insert_commit_run_sql
from ..main.functions.refresh_repos import run_sql as refresh_repos_run_sql
from ..main.functions.update_json import run_sql as update_json_run_sql
from ..main.functions.verify_session import run_sql as verify_session_run_sql


# v4.4.0
def run_sql(schema_editor):
    schema_editor.execute(
        """
         ---- Column Updates -----
        drop trigger repo_yaml_update on repos;
        drop trigger owner_yaml_updated on owners;

        alter table owners  drop column if exists errors;
        alter table owners  drop column if exists yaml_repoid;
        alter table commits drop column if exists logs;
        alter table commits drop column if exists archived;
        alter table pulls   rename column totals to diff;
        alter table pulls   drop column if exists changes;
        alter table pulls   drop column if exists base_branch;
        alter table pulls   drop column if exists head_branch;
        alter table repos   alter column yaml   set data type jsonb;
        alter table repos   alter column cache  set data type jsonb;
        alter table owners  alter column cache  set data type jsonb;
        alter table owners  alter column yaml   set data type jsonb;
        alter table commits alter column totals set data type jsonb;
        alter table commits alter column report set data type jsonb;
        alter table pulls   alter column diff   set data type jsonb;
        alter table pulls   alter column flare  set data type jsonb;
        alter table owners  alter column integration_id set data type integer;

        create trigger repo_yaml_update after update on repos
        for each row
        when (
            ((new.yaml->'codecov'->>'bot')::text is distinct from (old.yaml->'codecov'->>'bot')::text)
            or ((new.yaml->'codecov'->>'branch')::text is distinct from (old.yaml->'codecov'->>'branch')::text)
        )
        execute procedure repo_yaml_update();


        create trigger owner_yaml_updated before update on owners
        for each row
        when (
            ((new.yaml->'codecov'->>'bot')::text is distinct from (old.yaml->'codecov'->>'bot')::text)
            or ((new.yaml->'codecov'->>'branch')::text is distinct from (old.yaml->'codecov'->>'branch')::text)
        )
        execute procedure owner_yaml_updated();


        drop trigger pulls_before_insert on pulls;
        drop function pulls_insert();
        drop trigger pulls_before_update on pulls;
        drop function pulls_update();

        create or replace function pulls_drop_flare() returns trigger as $$
        begin
            new.flare = null;
            return new;
        end;
        $$ language plpgsql;

        create trigger pulls_before_update_drop_flare before update on pulls
        for each row
        when (new.state != 'open'::pull_state)
        execute procedure pulls_drop_flare();

        ---- Function Changes -----
        drop function if exists get_new_repos(int);
        drop function if exists get_pull(int, int);
        drop function if exists coverage(service, text, text, text, text);
        drop function if exists extract_totals(version smallint, files json, sessionids integer[]);
        drop function if exists get_commit(repoid, _commitid, path, tree_only);
        drop function if exists get_commit_on_branch(integer, text, text, boolean);
        drop function if exists get_totals_for_file(smallint, json);
        drop function if exists refresh_teams(service, json, integer);
        drop function if exists get_commit(integer, text, text, boolean);

        -- insert_commit.sql
        drop function if exists insert_commit(integer, text, text, integer, json);
    """
    )
    insert_commit_run_sql(schema_editor)

    schema_editor.execute(
        """
        -- aggregates.sql
        drop function if exists _pop_first_as_json(json[]) cascade;
        drop function if exists _max_coverage(json[]) cascade;
        drop function if exists _min_coverage(json[]) cascade;
        drop function _max_coverage(json[], json);
        drop function _min_coverage(json[], json);
        drop aggregate agg_totals(json);
        drop function _agg_report_totals(text[], json);
    """
    )
    aggregates_run_sql(schema_editor)

    schema_editor.execute(
        """
        -- coverage.sql
        drop function if exists get_coverage(service,citext,citext,citext);
    """
    )
    coverage_run_sql(schema_editor)

    schema_editor.execute(
        """
        -- get_access_token.sql
        drop function if exists get_access_token(int);
    """
    )
    get_access_token_run_sql(schema_editor)

    schema_editor.execute(
        """
        -- get_author.sql
        drop function if exists get_author(int);
    """
    )
    get_author_run_sql(schema_editor)

    schema_editor.execute(
        """
        -- get_commit.sql
        drop function if exists get_commit_totals(int, text);
        drop function if exists get_commit_totals(int, text, text);
        drop function if exists get_commit(repoid integer, _commitid text);
        drop function if exists get_commit_minimum(int, text);
        drop function if exists get_
        commit_on_branch(int, text);
    """
    )
    get_commit_run_sql(schema_editor)

    schema_editor.execute(
        """
        -- get_customer.sql
        drop function if exists get_customer(int);
    """
    )
    get_customer_run_sql(schema_editor)

    schema_editor.execute(
        """
        -- get_graph_for.sql
        drop function if exists sum_of_file_totals_filtering_sessionids(json, int[]);
        drop function if exists extract_totals(files json, sessionids int[]);
        drop function if exists list_sessionid_by_filtering_flags(sessions json, flags text[]);
        drop function if exists total_list_to_json(totals text[]);
        drop function if exists sum_session_totals(sessions json, flags text[]);
        drop function if exists get_graph_for_flare_pull(int, text, text, text[]);
        drop function if exists get_graph_for_flare_commit(int, text, text, text[]);
        drop function if exists get_graph_for_flare_branch(int, text, text, text[]);
        drop function if exists get_graph_for_totals_pull(int, text, text, text[]);
        drop function if exists get_graph_for_totals_commit(int, text, text, text[]);
        drop function if exists get_graph_for_totals_branch(int, text, text, text[]);
        drop function if exists get_graph_for_commits_pull(int, text, text, text[]);
        drop function if exists get_graph_for_commits_branch(int, text, text, text[]);
    """
    )
    get_graph_for_run_sql(schema_editor)

    schema_editor.execute(
        """
        -- get_ownerid.sql
        drop function if exists get_owner(service, citext);
        drop function if exists get_teams(service, integer[]);
    """
    )
    get_ownerid_run_sql(schema_editor)

    schema_editor.execute(
        """
        -- get_repo.sql
        drop function if exists get_repo(int);
        drop function if exists get_repo(int, citext);
        drop function if exists get_repo_by_token(uuid);
        drop function if exists get_repos(int, int, int);
    """
    )
    get_repo_run_sql(schema_editor)

    schema_editor.execute(
        """
        -- get_user.sql
        drop function if exists get_user(int);
        drop function if exists get_username(int);
        drop function if exists get_users(int[]);
    """
    )
    get_user_run_sql(schema_editor)

    schema_editor.execute(
        """
        -- refresh_repos.sql
        drop function if exists refresh_teams(service, json);
        drop function if exists refresh_repos(service, json, int, boolean);
    """
    )
    refresh_repos_run_sql(schema_editor)

    schema_editor.execute(
        """
        -- update_json.sql
        drop function if exists add_key_to_json(json, text, json);
        drop function if exists add_key_to_json(json, text, integer);
        drop function if exists add_key_to_json(json, text, text);
        drop function if exists remove_key_from_json(json, text);
        drop function if exists update_json(json, text, json);
        drop function if exists update_json(json, text, integer);
        drop function if exists update_json(json, text, text);
    """
    )
    update_json_run_sql(schema_editor)

    schema_editor.execute(
        """
        -- verify_session.sql
        drop function if exists verify_session(text, text, uuid, sessiontype);
    """
    )
    verify_session_run_sql(schema_editor)

    schema_editor.execute(
        """
        -- Trigger Changes --
        create or replace function commits_update_heads() returns trigger as $$
        begin

            if new.pullid is not null and new.merged is not true then
            -- update head of pulls
            update pulls p
                set updatestamp = now(),
                    head = case when head is not null
                                and (select timestamp > new.timestamp
                                    from commits c
                                    where c.repoid=new.repoid
                                    and c.commitid=p.head
                                    and c.deleted is not true
                                    limit 1)
                                then head
                                else new.commitid
                                end,
                    author = coalesce(author, new.author)
                where repoid = new.repoid
                and pullid = new.pullid;

            end if;

            -- update head of branches
            if new.branch is not null then
            update branches
                set updatestamp = now(),
                    authors = array_append_unique(coalesce(authors, '{}'::int[]), new.author),
                    head = case
                        when head is null then new.commitid
                        when (
                            head != new.commitid
                            and new.timestamp >= coalesce((select timestamp
                                                            from commits
                                                            where commitid=head
                                                            and deleted is not true
                                                            and repoid=new.repoid
                                                            limit 1), '-infinity'::timestamp)
                        ) then new.commitid
                        else head end
                where repoid = new.repoid
                and branch = new.branch;
            if not found then
                insert into branches (repoid, updatestamp, branch, head, authors)
                values (new.repoid, new.timestamp, new.branch, new.commitid,
                        case when new.author is not null then array[new.author] else null end);
            end if;
            end if;

            return null;
        end;
        $$ language plpgsql;

        create or replace function branches_update() returns trigger as $$
        declare _ownerid int;
        begin
            -- update repos cache if main branch
            update repos
            set updatestamp = now(),
                cache = update_json(cache::jsonb, 'commit', get_commit_minimum(new.repoid, new.head)::jsonb)
            where repoid = new.repoid
                and branch = new.branch
            returning ownerid into _ownerid;

            if found then
            -- default branch updated, so we can update the owners timestamp
            -- to refresh the team list
            update owners
            set updatestamp=now()
            where ownerid=_ownerid;
            end if;

            return null;
        end;
        $$ language plpgsql;


        create or replace function repos_before_insert_or_update() returns trigger as $$
        begin
            -- repo name changed or deleted
            update repos
            set name = null,
                deleted = true,
                active = false,
                activated = false
            where ownerid = new.ownerid
            and name = new.name;
            return new;
        end;
        $$ language plpgsql;


        create index commits_on_pull on commits (repoid, pullid) where deleted is not true;

        alter table commits drop column chunks;

        drop trigger commits_update_heads on commits;

        create trigger commits_update_heads after update on commits
        for each row
        when ((
            new.deleted is distinct from old.deleted
        ) or (
            new.state = 'complete'::commit_state
            and new.deleted is not true
            and
            (
            new.state is distinct from old.state
            or new.pullid is distinct from old.pullid
            or new.merged is distinct from old.merged
            or new.branch is distinct from old.branch
            )
        ))
        execute procedure commits_update_heads();
    """
    )
