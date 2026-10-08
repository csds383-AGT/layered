import os
from contextlib import contextmanager
from uuid import UUID

import psycopg
from psycopg.rows import dict_row, scalar_row
from psycopg.types.string import TextLoader

# ======================================================================
# Database
# ======================================================================

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


# ======================================================================
# Any table
# ======================================================================

def exists(table, record_id):
    return db.execute(f"SELECT 1 FROM {table} WHERE id = %s", [to_uuid(record_id)]).fetchone() is not None


def get(table, record_id):
    return db.execute(f"SELECT * FROM {table} WHERE id = %s", [to_uuid(record_id)]).fetchone()


def find(table, record_id, order_by="name"):
    if record_id is None:
        return db.execute(f"SELECT * FROM {table} ORDER BY {order_by}, id").fetchall()
    return db.execute(f"SELECT * FROM {table} WHERE id = %s", [to_uuid(record_id)]).fetchall()


def delete(table, record_id):
    return db.execute(f"DELETE FROM {table} WHERE id = %s", [to_uuid(record_id)]).rowcount > 0


def select_ids(query, record_id):
    return db.cursor(row_factory=scalar_row).execute(query, [to_uuid(record_id)]).fetchall()


# ======================================================================
# Concert events
# ======================================================================

def insert_concert(custom_id, name, description, available_tickets, ticket_price):
    # without a custom id the database generates one, and RETURNING gives back whichever id was used
    return db.execute(
        "INSERT INTO concert_events (id, name, description, available_tickets, ticket_price) "
        "VALUES (COALESCE(%s, uuidv7()), %s, %s, %s, %s) RETURNING id",
        [to_uuid(custom_id), name, description, available_tickets, ticket_price],
    ).fetchone()["id"]


def update_concert(event_id, name, description, available_tickets, ticket_price):
    db.execute(
        "UPDATE concert_events SET name = %s, description = %s, available_tickets = %s, ticket_price = %s "
        "WHERE id = %s",
        [name, description, available_tickets, ticket_price, to_uuid(event_id)],
    )


def artist_ids_for_event(event_id):
    return select_ids("SELECT artist_id FROM event_artists WHERE event_id = %s ORDER BY artist_id", event_id)


def category_ids_for_event(event_id):
    return select_ids("SELECT category_id FROM event_categories WHERE event_id = %s ORDER BY category_id", event_id)


def media_ids_for_event(event_id):
    return select_ids("SELECT id FROM media WHERE event_id = %s ORDER BY id", event_id)


# ======================================================================
# Artists and bookings
# ======================================================================

def insert_artist(custom_id, name, booking_contact):
    return db.execute(
        "INSERT INTO artists (id, name, booking_contact) VALUES (COALESCE(%s, uuidv7()), %s, %s) RETURNING id",
        [to_uuid(custom_id), name, booking_contact],
    ).fetchone()["id"]


def update_artist(artist_id, name, booking_contact):
    db.execute("UPDATE artists SET name = %s, booking_contact = %s WHERE id = %s",
               [name, booking_contact, to_uuid(artist_id)])


def event_ids_for_artist(artist_id):
    return select_ids("SELECT event_id FROM event_artists WHERE artist_id = %s ORDER BY event_id", artist_id)


def is_booked(event_id, artist_id):
    return db.execute("SELECT 1 FROM event_artists WHERE event_id = %s AND artist_id = %s",
                      [to_uuid(event_id), to_uuid(artist_id)]).fetchone() is not None


def book_artist(event_id, artist_id):
    db.execute("INSERT INTO event_artists (event_id, artist_id) VALUES (%s, %s)",
               [to_uuid(event_id), to_uuid(artist_id)])


def unbook_artist(event_id, artist_id):
    return db.execute("DELETE FROM event_artists WHERE event_id = %s AND artist_id = %s",
                      [to_uuid(event_id), to_uuid(artist_id)]).rowcount > 0


def artist_booking_summary(artist_id):
    summary = db.execute(
        "SELECT COUNT(*) - COUNT(DISTINCT e.name) AS duplicate_names, SUM(e.ticket_price) AS total_price "
        "FROM event_artists ea JOIN concert_events e ON e.id = ea.event_id WHERE ea.artist_id = %s",
        [to_uuid(artist_id)],
    ).fetchone()
    return summary["duplicate_names"], summary["total_price"] or 0


# ======================================================================
# Categories
# ======================================================================

def insert_category(custom_id, name, description):
    return db.execute(
        "INSERT INTO categories (id, name, description) VALUES (COALESCE(%s, uuidv7()), %s, %s) RETURNING id",
        [to_uuid(custom_id), name, description],
    ).fetchone()["id"]


def update_category(category_id, name, description):
    db.execute("UPDATE categories SET name = %s, description = %s WHERE id = %s",
               [name, description, to_uuid(category_id)])


def event_ids_for_category(category_id):
    return select_ids("SELECT event_id FROM event_categories WHERE category_id = %s ORDER BY event_id", category_id)


def is_in_category(event_id, category_id):
    return db.execute("SELECT 1 FROM event_categories WHERE event_id = %s AND category_id = %s",
                      [to_uuid(event_id), to_uuid(category_id)]).fetchone() is not None


def category_in_use(category_id):
    return db.execute("SELECT 1 FROM event_categories WHERE category_id = %s",
                      [to_uuid(category_id)]).fetchone() is not None


def add_event_to_category(event_id, category_id):
    db.execute("INSERT INTO event_categories (event_id, category_id) VALUES (%s, %s)",
               [to_uuid(event_id), to_uuid(category_id)])


def remove_event_from_category(event_id, category_id):
    return db.execute("DELETE FROM event_categories WHERE event_id = %s AND category_id = %s",
                      [to_uuid(event_id), to_uuid(category_id)]).rowcount > 0


# ======================================================================
# Media
# ======================================================================

def insert_media(custom_id, event_id, image_url):
    return db.execute(
        "INSERT INTO media (id, event_id, image_url) VALUES (COALESCE(%s, uuidv7()), %s, %s) RETURNING id",
        [to_uuid(custom_id), to_uuid(event_id), image_url],
    ).fetchone()["id"]


def update_media(media_id, event_id, image_url):
    db.execute("UPDATE media SET event_id = %s, image_url = %s WHERE id = %s",
               [to_uuid(event_id), image_url, to_uuid(media_id)])


def move_media(media_id, event_id):
    return db.execute("UPDATE media SET event_id = %s WHERE id = %s",
                      [to_uuid(event_id), to_uuid(media_id)]).rowcount > 0


def delete_media_from_event(media_id, event_id):
    return db.execute("DELETE FROM media WHERE id = %s AND event_id = %s",
                      [to_uuid(media_id), to_uuid(event_id)]).rowcount > 0
