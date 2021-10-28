# v4.4.9
def run_sql(schema_editor):
    schema_editor.execute(
        """
        alter table owners add column student boolean null;
        alter table owners add column student_updated_at timestamp;
        alter table owners add column student_created_at timestamp;


        -- new get customer to return student status
        create or replace function get_customer(int) returns jsonb as $$
        with data as (
            select t.stripe_customer_id,
                t.stripe_subscription_id,
                t.ownerid::text,
                t.service,
                t.service_id,
                t.plan_user_count,
                t.plan_provider,
                t.plan_auto_activate,
                t.plan_activated_users,
                t.plan,
                t.email,
                t.free,
                t.did_trial,
                t.invoice_details,
                t.yaml,
                t.student,
                t.student_created_at,
                t.student_updated_at,
                b.username as bot_username,
                get_users(t.admins) as admins,
                get_repos_activated($1::int) as repos_activated
            from owners t
            LEFT JOIN owners b ON (b.ownerid = t.bot)
            where t.ownerid = $1
            limit 1
        ) select to_jsonb(data) from data limit 1;
        $$ language sql stable strict;
    """
    )
