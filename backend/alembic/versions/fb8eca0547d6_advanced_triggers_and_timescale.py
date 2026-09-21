"""advanced_triggers_and_timescale

Revision ID: fb8eca0547d6
Revises: df1c2aa7702d
Create Date: 2026-09-21 14:08:48.666110

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fb8eca0547d6'
down_revision: Union[str, Sequence[str], None] = 'df1c2aa7702d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Convert tracks to TimescaleDB hypertable
    op.execute("""
        SELECT create_hypertable(
            'tracks',
            'recorded_at',
            chunk_time_interval => INTERVAL '7 days',
            if_not_exists => TRUE
        )
    """)

    # 2. Updated_at trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # 3. Attach updated_at trigger to each table that has updated_at
    for table in ['vessels', 'scenes', 'spills', 'drift_runs']:
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """)

    # 4. Audit log append-only protection
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is append-only';
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_audit_no_update
        BEFORE UPDATE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();
    """)

    op.execute("""
        CREATE TRIGGER trg_audit_no_delete
        BEFORE DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();
    """)

    # 5. Dossier immutability after finalized
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_finalized_dossier_change()
        RETURNS TRIGGER AS $$
        BEGIN
            IF OLD.status = 'finalized' THEN
                RAISE EXCEPTION 'Finalized dossiers are immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_dossier_immutable
        BEFORE UPDATE ON dossiers
        FOR EACH ROW EXECUTE FUNCTION prevent_finalized_dossier_change();
    """)

    # 6. Roles (skip if they already exist)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_runtime') THEN
                CREATE ROLE app_runtime NOLOGIN;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'readonly') THEN
                CREATE ROLE readonly NOLOGIN;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'audit_writer') THEN
                CREATE ROLE audit_writer NOLOGIN;
            END IF;
        END $$;
    """)

    # 7. Grants
    op.execute("GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO app_runtime")
    op.execute("REVOKE UPDATE, DELETE ON audit_log FROM app_runtime")
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly")
    op.execute("GRANT INSERT ON audit_log TO audit_writer")


def downgrade() -> None:
    """Downgrade schema."""
    # Reverse triggers
    op.execute("DROP TRIGGER IF EXISTS trg_dossier_immutable ON dossiers;")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_no_delete ON audit_log;")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_no_update ON audit_log;")
    for table in ['vessels', 'scenes', 'spills', 'drift_runs']:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table};")

    # Reverse functions
    op.execute("DROP FUNCTION IF EXISTS prevent_finalized_dossier_change();")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_modification();")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at();")

    # Reverse roles and grants
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'audit_writer') THEN
                DROP ROLE audit_writer;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'readonly') THEN
                DROP ROLE readonly;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_runtime') THEN
                DROP ROLE app_runtime;
            END IF;
        END $$;
    """)
