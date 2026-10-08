import os
from contextlib import contextmanager
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import namedtuple_row, scalar_row
from psycopg.sql import SQL, Identifier, Placeholder
from psycopg.types.string import TextLoader

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://festhub:festhub@localhost:5433/festhub")

db = psycopg.Connection[Any].connect(DATABASE_URL, autocommit=True, row_factory=namedtuple_row)
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
    query = SQL("SELECT * FROM {} WHERE id = %s").format(Identifier(table))
    return db.execute(query, [to_uuid(record_id)]).fetchone()


def find(table, record_id, order_by):
    if record_id is not None:
        row = get(table, record_id)
        return [row] if row else []
    query = SQL("SELECT * FROM {} ORDER BY {}, id").format(Identifier(table), Identifier(order_by))
    return db.execute(query).fetchall()


def insert(table, custom_id, record):
    # returns None when the custom id is already taken
    values = vars(record)
    query = SQL(
        "INSERT INTO {} (id, {}) VALUES (COALESCE(%(id)s, uuidv7()), {}) ON CONFLICT (id) DO NOTHING RETURNING id"
    ).format(Identifier(table), SQL(", ").join(map(Identifier, values)), SQL(", ").join(map(Placeholder, values)))
    row = db.execute(query, dict(values, id=custom_id)).fetchone()
    return None if row is None else row.id


def update(table, record_id, changes):
    # values left as None keep the column's current value
    values = vars(changes)
    assignments = SQL(", ").join(
        SQL("{0} = COALESCE({1}, {0})").format(Identifier(column), Placeholder(column)) for column in values
    )
    query = SQL("UPDATE {} SET {} WHERE id = %(id)s RETURNING *").format(Identifier(table), assignments)
    return db.execute(query, dict(values, id=to_uuid(record_id))).fetchone()


def delete(table, record_id):
    query = SQL("DELETE FROM {} WHERE id = %s").format(Identifier(table))
    return db.execute(query, [to_uuid(record_id)]).rowcount > 0


def link(table, event_id, other_id):
    # returns False when the two are already linked
    query = SQL("INSERT INTO {} VALUES (%s, %s) ON CONFLICT DO NOTHING").format(Identifier(table))
    return db.execute(query, [to_uuid(event_id), to_uuid(other_id)]).rowcount > 0


def unlink(table, column, event_id, other_id):
    query = SQL("DELETE FROM {} WHERE event_id = %s AND {} = %s").format(Identifier(table), Identifier(column))
    return db.execute(query, [to_uuid(event_id), to_uuid(other_id)]).rowcount > 0


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
