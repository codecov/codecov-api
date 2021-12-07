def run_sql(schema_editor):
    schema_editor.execute(
        """
        -- EOF
        --
        -- Create model CommitReport
        --
        CREATE TABLE "reports_commitreport" (
            "id" bigserial NOT NULL PRIMARY KEY,
            "external_id" uuid NOT NULL,
            "created_at" timestamp with time zone NOT NULL,
            "updated_at" timestamp with time zone NOT NULL,
            "commit_id" bigint NOT NULL
        );
        --
        -- Create model ReportDetails
        --
        CREATE TABLE "reports_reportdetails" (
            "id" bigserial NOT NULL PRIMARY KEY,
            "external_id" uuid NOT NULL,
            "created_at" timestamp with time zone NOT NULL,
            "updated_at" timestamp with time zone NOT NULL,
            "files_array" jsonb[] NOT NULL,
            "report_id" bigint NOT NULL UNIQUE
        );
        --
        -- Create model ReportLevelTotals
        --
        CREATE TABLE "reports_reportleveltotals" (
            "id" bigserial NOT NULL PRIMARY KEY,
            "external_id" uuid NOT NULL,
            "created_at" timestamp with time zone NOT NULL,
            "updated_at" timestamp with time zone NOT NULL,
            "branches" integer NOT NULL,
            "coverage" numeric(7, 2) NOT NULL,
            "hits" integer NOT NULL,
            "lines" integer NOT NULL,
            "methods" integer NOT NULL,
            "misses" integer NOT NULL,
            "partials" integer NOT NULL,
            "files" integer NOT NULL,
            "report_id" bigint NOT NULL UNIQUE
        );
        --
        -- Create model ReportSession
        --
        CREATE TABLE "reports_upload" (
            "id" bigserial NOT NULL PRIMARY KEY,
            "external_id" uuid NOT NULL,
            "created_at" timestamp with time zone NOT NULL,
            "updated_at" timestamp with time zone NOT NULL,
            "build_code" text NULL,
            "build_url" text NULL,
            "env" jsonb NULL,
            "job_code" text NULL,
            "name" varchar(100) NULL,
            "provider" varchar(50) NULL,
            "state" varchar(100) NOT NULL,
            "storage_path" text NOT NULL,
            "order_number" integer NULL,
            "upload_extras" jsonb NOT NULL,
            "upload_type" varchar(100) NOT NULL
        );
        --
        -- Create model ReportSessionError
        --
        CREATE TABLE "reports_uploaderror" (
            "id" bigserial NOT NULL PRIMARY KEY,
            "external_id" uuid NOT NULL,
            "created_at" timestamp with time zone NOT NULL,
            "updated_at" timestamp with time zone NOT NULL,
            "error_code" varchar(100) NOT NULL,
            "error_params" jsonb NOT NULL,
            "upload_id" bigint NOT NULL
        );
        --
        -- Create model ReportSessionFlagMembership
        --
        CREATE TABLE "reports_uploadflagmembership" (
            "id" bigserial NOT NULL PRIMARY KEY
        );
        --
        -- Create model RepositoryFlag
        --
        CREATE TABLE "reports_repositoryflag" (
            "id" bigserial NOT NULL PRIMARY KEY,
            "external_id" uuid NOT NULL,
            "created_at" timestamp with time zone NOT NULL,
            "updated_at" timestamp with time zone NOT NULL,
            "flag_name" varchar(255) NOT NULL,
            "repository_id" integer NOT NULL
        );
        --
        -- Create model SessionLevelTotals
        --
        CREATE TABLE "reports_uploadleveltotals" (
            "id" bigserial NOT NULL PRIMARY KEY,
            "external_id" uuid NOT NULL,
            "created_at" timestamp with time zone NOT NULL,
            "updated_at" timestamp with time zone NOT NULL,
            "branches" integer NOT NULL,
            "coverage" numeric(7, 2) NOT NULL,
            "hits" integer NOT NULL,
            "lines" integer NOT NULL,
            "methods" integer NOT NULL,
            "misses" integer NOT NULL,
            "partials" integer NOT NULL,
            "files" integer NOT NULL,
            "upload_id" bigint NOT NULL UNIQUE
        );
        --
        -- Add field flag to reportsessionflagmembership
        --
        ALTER TABLE "reports_uploadflagmembership" ADD COLUMN "flag_id" bigint NOT NULL;
        --
        -- Add field report_session to reportsessionflagmembership
        --
        ALTER TABLE "reports_uploadflagmembership" ADD COLUMN "upload_id" bigint NOT NULL;
        --
        -- Add field flags to reportsession
        --
        --
        -- Add field report to reportsession
        --
        ALTER TABLE "reports_upload" ADD COLUMN "report_id" bigint NOT NULL;
        ALTER TABLE "reports_commitreport" ADD CONSTRAINT "reports_commitreport_commit_id_06d0bd39_fk_commits_id" FOREIGN KEY ("commit_id") REFERENCES "commits" ("id") DEFERRABLE INITIALLY DEFERRED;
        CREATE INDEX "reports_commitreport_commit_id_06d0bd39" ON "reports_commitreport" ("commit_id");
        ALTER TABLE "reports_reportdetails" ADD CONSTRAINT "reports_reportdetail_report_id_4681bfd3_fk_reports_c" FOREIGN KEY ("report_id") REFERENCES "reports_commitreport" ("id") DEFERRABLE INITIALLY DEFERRED;
        ALTER TABLE "reports_reportleveltotals" ADD CONSTRAINT "reports_reportlevelt_report_id_b690dffa_fk_reports_c" FOREIGN KEY ("report_id") REFERENCES "reports_commitreport" ("id") DEFERRABLE INITIALLY DEFERRED;
        ALTER TABLE "reports_uploaderror" ADD CONSTRAINT "reports_reportsessio_report_session_id_bb6563f1_fk_reports_r" FOREIGN KEY ("upload_id") REFERENCES "reports_upload" ("id") DEFERRABLE INITIALLY DEFERRED;
        CREATE INDEX "reports_uploaderror_report_session_id_bb6563f1" ON "reports_uploaderror" ("upload_id");
        ALTER TABLE "reports_repositoryflag" ADD CONSTRAINT "reports_repositoryflag_repository_id_9b64b64c_fk_repos_repoid" FOREIGN KEY ("repository_id") REFERENCES "repos" ("repoid") DEFERRABLE INITIALLY DEFERRED;
        CREATE INDEX "reports_repositoryflag_repository_id_9b64b64c" ON "reports_repositoryflag" ("repository_id");
        ALTER TABLE "reports_uploadleveltotals" ADD CONSTRAINT "reports_sessionlevel_report_session_id_e2cd6669_fk_reports_r" FOREIGN KEY ("upload_id") REFERENCES "reports_upload" ("id") DEFERRABLE INITIALLY DEFERRED;
        CREATE INDEX "reports_uploadflagmembership_flag_id_59edee69" ON "reports_uploadflagmembership" ("flag_id");
        ALTER TABLE "reports_uploadflagmembership" ADD CONSTRAINT "reports_reportsessio_flag_id_59edee69_fk_reports_r" FOREIGN KEY ("flag_id") REFERENCES "reports_repositoryflag" ("id") DEFERRABLE INITIALLY DEFERRED;
        CREATE INDEX "reports_uploadflagmembership_report_session_id_7d7f9546" ON "reports_uploadflagmembership" ("upload_id");
        ALTER TABLE "reports_uploadflagmembership" ADD CONSTRAINT "reports_reportsessio_report_session_id_7d7f9546_fk_reports_r" FOREIGN KEY ("upload_id") REFERENCES "reports_upload" ("id") DEFERRABLE INITIALLY DEFERRED;
        CREATE INDEX "reports_upload_report_id_f6b4ffae" ON "reports_upload" ("report_id");
        ALTER TABLE "reports_upload" ADD CONSTRAINT "reports_reportsessio_report_id_f6b4ffae_fk_reports_c" FOREIGN KEY ("report_id") REFERENCES "reports_commitreport" ("id") DEFERRABLE INITIALLY DEFERRED;
    """
    )
