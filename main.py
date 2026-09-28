import sqlite3
import typer
from uuid import UUID, uuid4
from email_validator import EmailNotValidError, validate_email

SCHEMA = """
         CREATE TABLE IF NOT EXISTS concert_events
         (
             id                TEXT PRIMARY KEY NOT NULL DEFAULT (new_uuid()),
             name              TEXT             NOT NULL CHECK (length(name) <= 2000),
             description       TEXT             NOT NULL CHECK (length(description) <= 10000),
             available_tickets INTEGER          NOT NULL
                 CHECK (typeof(available_tickets) = 'integer' AND available_tickets >= 0),
             ticket_price      INTEGER          NOT NULL
                 CHECK (typeof(ticket_price) = 'integer' AND ticket_price > 0),
             CHECK (available_tickets != 0 OR ticket_price <= 10000)
         );

         CREATE TABLE IF NOT EXISTS artists
         (
             id              TEXT PRIMARY KEY NOT NULL DEFAULT (new_uuid()),
             name            TEXT             NOT NULL CHECK (length(name) <= 2000),
             booking_contact TEXT             NOT NULL CHECK (is_email(booking_contact))
         );

         CREATE TABLE IF NOT EXISTS event_artists
         (
             event_id  TEXT NOT NULL REFERENCES concert_events (id) ON DELETE CASCADE,
             artist_id TEXT NOT NULL REFERENCES artists (id) ON DELETE CASCADE,
             PRIMARY KEY (event_id, artist_id)
         );

         """


def is_email(value):
    if not isinstance(value, str):
        return False
    try:
        validate_email(value, check_deliverability=False)
        return True
    except EmailNotValidError:
        return False


# TODO: testing only, pls delete later
def show_tables(db):
    for table in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'"):
        typer.echo(f"yay u made this table: {table[0]}")


def main():
    db = sqlite3.connect(":memory:")
    db.create_function("new_uuid", 0, lambda: str(uuid4()))
    db.create_function("is_email", 1, is_email, deterministic=True)
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(SCHEMA)
    show_tables(db)
    db.close()


if __name__ == "__main__":
    typer.run(main)
