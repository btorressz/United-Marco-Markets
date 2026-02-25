import os
import logging
from pathlib import Path

import psycopg2
import psycopg2.extras
import psycopg2.pool

logger = logging.getLogger(__name__)

_pool: psycopg2.pool.SimpleConnectionPool | None = None

MIGRATIONS_PATH = Path(__file__).parent / "migrations.sql"


def _get_database_url() -> str:
    return os.environ.get("DATABASE_URL", "")


def _get_pool() -> psycopg2.pool.SimpleConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        url = _get_database_url()
        if not url:
            raise RuntimeError("DATABASE_URL not set")
        _pool = psycopg2.pool.SimpleConnectionPool(1, 10, url)
        logger.info("Database connection pool created")
    return _pool


def get_connection():
    pool = _get_pool()
    conn = pool.getconn()
    conn.autocommit = True
    return conn


def release_connection(conn):
    try:
        pool = _get_pool()
        pool.putconn(conn)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


def execute_query(sql: str, params: tuple | list | None = None) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            if cur.description:
                rows = cur.fetchall()
                return [dict(row) for row in rows]
            return []
    finally:
        release_connection(conn)


def execute_write(sql: str, params: tuple | list | None = None) -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount
    finally:
        release_connection(conn)


def execute_returning(sql: str, params: tuple | list | None = None) -> dict | None:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            if cur.description:
                row = cur.fetchone()
                return dict(row) if row else None
            return None
    finally:
        release_connection(conn)


def init_db() -> None:
    if not MIGRATIONS_PATH.exists():
        logger.warning("Migrations file not found at %s", MIGRATIONS_PATH)
        return
    sql = MIGRATIONS_PATH.read_text()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        logger.info("Database migrations applied successfully")
    except Exception:
        logger.error("Failed to apply migrations", exc_info=True)
        raise
    finally:
        release_connection(conn)


def check_connection() -> bool:
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        finally:
            release_connection(conn)
    except Exception:
        return False
