# 4.5.1
def run_sql(schema_editor):
    schema_editor.execute(
        """
        -- create enums used by commit_notifications table
        create type notifications as enum('comment', 'gitter', 'hipchat', 'irc', 'slack', 'status_changes', 'status_patch', 'status_project', 'webhook', 'checks_patch', 'checks_project', 'checks_changes');
        create type decorations as enum('standard', 'upgrade');
        create type commit_notification_state as enum('pending', 'success', 'error');

        -- Here we're commenting out all plan related migrations below because they break on enterprise
        -- these migrations have been run already for production, but can break some production
        -- deployments. Specifically the setting of the plan column to a new default causes problems with 
        -- web's ability to migrate effectively in some scenarios. 

        -- If you're starting from scratch in dev, you will need to run the below migrations manually,
        -- or comment out these migrations before starting up codecov.io for the first time. 

        -- This isn't ideal, and will hopefully be addressed when we move all migrations to Django.

        -- Transaction friendly enum column upates. See: https://stackoverflow.com/questions/1771543/adding-a-new-value-to-an-existing-enum-type#7834949
        -- NOTE: we will not change the plan default yet

        -- first remove the default from plan column otherwise we'll get an error below with trying to cast the default
        -- alter table owners alter column plan drop default;

        -- rename the old enum
        -- alter type plans rename to plans__;

        -- create the new enum adding users-pr-inappm and users-pr-inappy plans
        -- create type plans as enum('5m', '5y', '25m', '25y', '50m', '50y', '100m', '100y', '250m', '250y', '500m', '500y', '1000m', '1000y', '1m', '1y',
        --                           'v4-10m', 'v4-10y', 'v4-20m', 'v4-20y', 'v4-50m', 'v4-50y', 'v4-125m', 'v4-125y', 'v4-300m', 'v4-300y',
        --                          'users', 'users-inappm', 'users-inappy', 'users-pr-inappm', 'users-pr-inappy', 'users-free');

        -- use the new enum
        -- alter table owners alter column plan type plans using plan::text::plans;


        --ALTER TABLE ONLY owners ALTER COLUMN plan SET DEFAULT 'users-free';

        -- drop the old enum
        -- drop type plans__;
    """
    )
