import sqlite3
from contextlib import contextmanager
from uuid import uuid4

# ======================================================================
# Database
# ======================================================================

SCHEMA = """
         CREATE TABLE concert_events
         (
             id                TEXT PRIMARY KEY NOT NULL DEFAULT (new_uuid()),
             name              TEXT             NOT NULL,
             description       TEXT             NOT NULL,
             available_tickets INTEGER          NOT NULL,
             ticket_price      INTEGER          NOT NULL
         );

         CREATE TABLE artists
         (
             id              TEXT PRIMARY KEY NOT NULL DEFAULT (new_uuid()),
             name            TEXT             NOT NULL,
             booking_contact TEXT             NOT NULL
         );

         CREATE TABLE event_artists
         (
             event_id  TEXT NOT NULL REFERENCES concert_events (id) ON DELETE CASCADE,
             artist_id TEXT NOT NULL REFERENCES artists (id) ON DELETE CASCADE,
             PRIMARY KEY (event_id, artist_id)
         );

         CREATE TABLE categories
         (
             id          TEXT PRIMARY KEY NOT NULL DEFAULT (new_uuid()),
             name        TEXT             NOT NULL,
             description TEXT             NOT NULL
         );

         CREATE TABLE event_categories
         (
             event_id    TEXT NOT NULL REFERENCES concert_events (id) ON DELETE CASCADE,
             category_id TEXT NOT NULL REFERENCES categories (id) ON DELETE CASCADE,
             PRIMARY KEY (event_id, category_id)
         );

         CREATE TABLE media
         (
             id        TEXT PRIMARY KEY NOT NULL DEFAULT (new_uuid()),
             event_id  TEXT             NOT NULL REFERENCES concert_events (id) ON DELETE CASCADE,
             image_url TEXT             NOT NULL
         );
         """

db = sqlite3.connect(":memory:")
db.row_factory = sqlite3.Row  # lets rows be read by column name like row["id"]
db.create_function("new_uuid", 0, lambda: str(uuid4()))
db.execute("PRAGMA foreign_keys = ON")
db.executescript(SCHEMA)


@contextmanager
def transaction():
    # commits when the block finishes and rolls back if it raises, so a failed command changes nothing
    with db:
        yield


# ======================================================================
# Any table
# ======================================================================

def exists(table, record_id):
    return get(table, record_id) is not None


def get(table, record_id):
    return db.execute(f"SELECT * FROM {table} WHERE id = ?", [record_id]).fetchone()


def find(table, record_id, order_by="name"):
    return db.execute(
        f"SELECT * FROM {table} WHERE ? IS NULL OR id = ? ORDER BY {order_by}", [record_id, record_id]
    ).fetchall()


def delete(table, record_id):
    return db.execute(f"DELETE FROM {table} WHERE id = ?", [record_id]).rowcount > 0


def select_ids(query, record_id):
    return [row[0] for row in db.execute(query, [record_id])]


# ======================================================================
# Concert events
# ======================================================================

def insert_concert(custom_id, name, description, available_tickets, ticket_price):
    # without a custom id the database generates one, and RETURNING gives back whichever id was used
    return db.execute(
        "INSERT INTO concert_events VALUES (COALESCE(?, new_uuid()), ?, ?, ?, ?) RETURNING id",
        [custom_id, name, description, available_tickets, ticket_price],
    ).fetchone()["id"]


def update_concert(event_id, name, description, available_tickets, ticket_price):
    db.execute(
        "UPDATE concert_events SET name = ?, description = ?, available_tickets = ?, ticket_price = ? "
        "WHERE id = ?",
        [name, description, available_tickets, ticket_price, event_id],
    )


def artist_ids_for_event(event_id):
    return select_ids("SELECT artist_id FROM event_artists WHERE event_id = ?", event_id)


def category_ids_for_event(event_id):
    return select_ids("SELECT category_id FROM event_categories WHERE event_id = ?", event_id)


def media_ids_for_event(event_id):
    return select_ids("SELECT id FROM media WHERE event_id = ?", event_id)


# ======================================================================
# Artists and bookings
# ======================================================================

def insert_artist(custom_id, name, booking_contact):
    return db.execute(
        "INSERT INTO artists VALUES (COALESCE(?, new_uuid()), ?, ?) RETURNING id",
        [custom_id, name, booking_contact],
    ).fetchone()["id"]


def update_artist(artist_id, name, booking_contact):
    db.execute("UPDATE artists SET name = ?, booking_contact = ? WHERE id = ?", [name, booking_contact, artist_id])


def event_ids_for_artist(artist_id):
    return select_ids("SELECT event_id FROM event_artists WHERE artist_id = ?", artist_id)


def is_booked(event_id, artist_id):
    return db.execute("SELECT 1 FROM event_artists WHERE event_id = ? AND artist_id = ?",
                      [event_id, artist_id]).fetchone() is not None


def book_artist(event_id, artist_id):
    db.execute("INSERT INTO event_artists VALUES (?, ?)", [event_id, artist_id])


def unbook_artist(event_id, artist_id):
    return db.execute("DELETE FROM event_artists WHERE event_id = ? AND artist_id = ?",
                      [event_id, artist_id]).rowcount > 0


def artist_booking_summary(artist_id):
    duplicate_names, total_price = db.execute(
        "SELECT COUNT(*) - COUNT(DISTINCT e.name), SUM(e.ticket_price) "
        "FROM event_artists ea JOIN concert_events e ON e.id = ea.event_id WHERE ea.artist_id = ?",
        [artist_id],
    ).fetchone()
    return duplicate_names, total_price or 0


# ======================================================================
# Categories
# ======================================================================

def insert_category(custom_id, name, description):
    return db.execute(
        "INSERT INTO categories VALUES (COALESCE(?, new_uuid()), ?, ?) RETURNING id",
        [custom_id, name, description],
    ).fetchone()["id"]


def update_category(category_id, name, description):
    db.execute("UPDATE categories SET name = ?, description = ? WHERE id = ?", [name, description, category_id])


def event_ids_for_category(category_id):
    return select_ids("SELECT event_id FROM event_categories WHERE category_id = ?", category_id)


def is_in_category(event_id, category_id):
    return db.execute("SELECT 1 FROM event_categories WHERE event_id = ? AND category_id = ?",
                      [event_id, category_id]).fetchone() is not None


def category_in_use(category_id):
    return db.execute("SELECT 1 FROM event_categories WHERE category_id = ?", [category_id]).fetchone() is not None


def add_event_to_category(event_id, category_id):
    db.execute("INSERT INTO event_categories VALUES (?, ?)", [event_id, category_id])


def remove_event_from_category(event_id, category_id):
    return db.execute("DELETE FROM event_categories WHERE event_id = ? AND category_id = ?",
                      [event_id, category_id]).rowcount > 0


# ======================================================================
# Media
# ======================================================================

def insert_media(custom_id, event_id, image_url):
    return db.execute(
        "INSERT INTO media VALUES (COALESCE(?, new_uuid()), ?, ?) RETURNING id",
        [custom_id, event_id, image_url],
    ).fetchone()["id"]


def update_media(media_id, event_id, image_url):
    db.execute("UPDATE media SET event_id = ?, image_url = ? WHERE id = ?", [event_id, image_url, media_id])


def move_media(media_id, event_id):
    return db.execute("UPDATE media SET event_id = ? WHERE id = ?", [event_id, media_id]).rowcount > 0


def delete_media_from_event(media_id, event_id):
    return db.execute("DELETE FROM media WHERE id = ? AND event_id = ?", [media_id, event_id]).rowcount > 0
