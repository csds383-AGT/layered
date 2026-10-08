import os
from contextlib import contextmanager
from uuid import UUID

import psycopg
from psycopg.rows import dict_row, scalar_row
from psycopg.types.string import TextLoader

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://festhub:festhub@localhost:5433/festhub")

db = psycopg.connect(DATABASE_URL, autocommit=True, row_factory=dict_row)
db.adapters.register_loader("uuid", TextLoader)


@contextmanager
def transaction():
    # commits when the block finishes and rolls back if it raises, so a failed command changes nothing
    with db.transaction():
        yield


def to_uuid(record_id):
    # an id that isn't a valid UUID can't match any row, so send NULL instead of letting Postgres raise
    try:
        return UUID(record_id)
    except (TypeError, ValueError):
        return None


def get(table, record_id):
    return db.execute(f"SELECT * FROM {table} WHERE id = %s", [to_uuid(record_id)]).fetchone()


def find(table, record_id, order_by):
    if record_id is None:
        return db.execute(f"SELECT * FROM {table} ORDER BY {order_by}, id").fetchall()
    return db.execute(f"SELECT * FROM {table} WHERE id = %s", [to_uuid(record_id)]).fetchall()


def insert(table, custom_id, **values):
    # returns None when the custom id is already taken
    columns = ", ".join(values)
    placeholders = ", ".join(["%s"] * len(values))
    row = db.execute(
        f"INSERT INTO {table} (id, {columns}) VALUES (COALESCE(%s, uuidv7()), {placeholders}) "
        "ON CONFLICT (id) DO NOTHING RETURNING id",
        [custom_id, *values.values()],
    ).fetchone()
    return row and row["id"]


def update(table, record_id, **values):
    # values left as None keep the column's current value
    assignments = ", ".join(f"{column} = COALESCE(%s, {column})" for column in values)
    return db.execute(
        f"UPDATE {table} SET {assignments} WHERE id = %s RETURNING *", [*values.values(), to_uuid(record_id)]
    ).fetchone()


def delete(table, record_id):
    return db.execute(f"DELETE FROM {table} WHERE id = %s", [to_uuid(record_id)]).rowcount > 0


def link(table, event_id, other_id):
    # returns False when the two are already linked
    return db.execute(f"INSERT INTO {table} VALUES (%s, %s) ON CONFLICT DO NOTHING",
                      [to_uuid(event_id), to_uuid(other_id)]).rowcount > 0


def unlink(table, column, event_id, other_id):
    return db.execute(f"DELETE FROM {table} WHERE event_id = %s AND {column} = %s",
                      [to_uuid(event_id), to_uuid(other_id)]).rowcount > 0


def artist_booking_summary(artist_id):
    return db.execute(
        "SELECT COUNT(*) - COUNT(DISTINCT e.name) AS duplicate_names, "
        "COALESCE(SUM(e.ticket_price), 0) AS total_price "
        "FROM event_artists ea JOIN concert_events e ON e.id = ea.event_id WHERE ea.artist_id = %s",
        [to_uuid(artist_id)],
    ).fetchone()


def delete_unused_categories(category_ids):
    return db.cursor(row_factory=scalar_row).execute(
        "WITH deleted AS (DELETE FROM categories c WHERE id = ANY(%s) "
        "AND NOT EXISTS (SELECT 1 FROM event_categories WHERE category_id = c.id) RETURNING id) "
        "SELECT id FROM deleted ORDER BY id",
        [category_ids],
    ).fetchall()
