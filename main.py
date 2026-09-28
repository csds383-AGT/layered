import sqlite3
import typer
from uuid import UUID, uuid4

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
             booking_contact TEXT             NOT NULL
         );

         CREATE TABLE IF NOT EXISTS event_artists
         (
             event_id  TEXT NOT NULL REFERENCES concert_events (id) ON DELETE CASCADE,
             artist_id TEXT NOT NULL REFERENCES artists (id) ON DELETE CASCADE,
             PRIMARY KEY (event_id, artist_id)
         );

         """


# TODO: testing only, pls delete later
def show_tables(db):
    for table in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'"):
        typer.echo(f"yay u made this table: {table[0]}")


def main():
    db = sqlite3.connect(":memory:")
    db.create_function("new_uuid", 0, lambda: str(uuid4()))
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(SCHEMA)
    show_tables(db)
    db.close()


if __name__ == "__main__":
    typer.run(main)
