"""Direct PostgreSQL adapter; no Supabase account management token required.

Use a dedicated DB role, TLS and a private persistent state directory. Role
provisioning is separate: this module never grants rights or changes schema.
"""
from contextlib import contextmanager
import json
import os
from urllib.parse import urlsplit, parse_qs

from .publication_database import ManagementClient, PROJECT, TABLES, condition, canonical


class PostgresClient(ManagementClient):
    def __init__(self, dsn=None):
        self.project = PROJECT
        self.dsn = dsn or os.environ['KIDSNEWS_DATABASE_URL']
        parts = urlsplit(self.dsn)
        if parts.scheme not in ('postgres', 'postgresql') or not parts.hostname:
            raise ValueError('Postgres URL required')
        if parts.hostname != f'db.{PROJECT}.supabase.co' and not (
            parts.hostname.endswith('.pooler.supabase.com') and
            (parts.username or '').endswith('.'+PROJECT)):
            raise ValueError('Database URL must target the approved Supabase project')
        if parse_qs(parts.query).get('sslmode', [''])[0] not in ('require', 'verify-ca', 'verify-full'):
            raise ValueError('Database connection must explicitly require TLS')
        if parts.port not in (None, 5432):
            raise ValueError('Use direct/session port 5432; transaction pooling cannot hold publication session locks')
        self.connect = None

    def connection(self):
        if self.connect is None:
            import psycopg
            self.connect = psycopg.connect
        return self.connect(self.dsn, autocommit=True, connect_timeout=15)

    def query(self, sql):
        from psycopg.rows import dict_row
        with self.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, prepare=False)
                # Paired script ends with COMMIT, so no rows are returned.
                return cur.fetchall() if cur.description is not None else []

    def preflight(self):
        """Read-only permission check before expensive models/website mutations."""
        rows = self.query("select c.relname, "
            "has_table_privilege(current_user,c.oid,'SELECT') and "
            "has_table_privilege(current_user,c.oid,'INSERT') and "
            "has_table_privilege(current_user,c.oid,'UPDATE') and "
            "has_table_privilege(current_user,c.oid,'DELETE') as writable, "
            "pg_has_role(current_user,c.relowner,'USAGE') as owns "
            "from pg_class c join pg_namespace n on n.oid=c.relnamespace "
            "where n.nspname='public' and c.relname in "
            "('redesign_runs','redesign_stories','redesign_search_index','redesign_source_configs')")
        if {r['relname'] for r in rows} != set(TABLES) or any(not r['writable'] for r in rows):
            raise ValueError('Database schema/write permissions missing; no website publication')
        if not next(r for r in rows if r['relname']=='redesign_search_index')['owns']:
            raise ValueError('Exact rollback needs search table ownership; review role before publishing')

    @contextmanager
    def publication_lock(self):
        # Session lock across Storage + DB operations. No long DB transaction.
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select pg_try_advisory_lock(hashtext('kidsnews-python-publication'))")
                if not cur.fetchone()[0]:
                    raise ValueError('Another Python publisher is active')
                try:
                    yield
                finally:
                    cur.execute("select pg_advisory_unlock(hashtext('kidsnews-python-publication'))")

    def verify_database(self, state):
        from pathlib import Path
        root = Path(state)
        scope = json.loads((root/'scope.json').read_bytes())
        expected = json.loads((root/'after.json').read_bytes())
        actual = self.snapshot(scope)['rows']
        for table in TABLES:
            if canonical(actual[table], table) != canonical(expected[table], table):
                raise ValueError('Database readback mismatch: '+table)
        return True
