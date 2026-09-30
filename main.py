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


def check_sold_out_price(available_tickets, ticket_price):
    if available_tickets == 0 and ticket_price > 10000:
        raise ValueError("a sold out event (0 tickets) cannot cost more than $100.00")


def check_artist_rules(db, artist_id):
    # run after booking an artist or changing an event's name/price inside the same `with db:` so a failure undoes the change
    events = db.execute("""
                        SELECT concert_events.name, concert_events.ticket_price
                        FROM concert_events
                                 JOIN event_artists ON concert_events.id = event_artists.event_id
                        WHERE event_artists.artist_id = ?
                        """, (artist_id,)).fetchall()
    names = [name for name, price in events]
    if len(names) != len(set(names)):
        raise ValueError(f"artist {artist_id} is already booked for an event with this name")
    if sum(price for name, price in events) > 50_000_000:
        raise ValueError(f"artist {artist_id}'s total ticket prices cannot exceed $500,000.00")


# TODO: testing only, pls delete later
def show_tables(db):
    for table in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'"):
        typer.echo(f"yay u made this table: {table[0]}")


# set up typer and every command. with subcommands
app = typer.Typer()
create_app = typer.Typer()
app.add_typer(create_app, name="create")
show_app = typer.Typer()
app.add_typer(show_app, name="show")
update_app = typer.Typer()
app.add_typer(update_app, name="update")
delete_app = typer.Typer()
app.add_typer(delete_app, name="delete")

_db = None


def get_db():
    global _db
    if _db is None:
        _db = sqlite3.connect(":memory:")
        _db.create_function("new_uuid", 0, lambda: str(uuid4()))
        _db.create_function("is_email", 1, is_email, deterministic=True)
        _db.execute("PRAGMA foreign_keys = ON")
        _db.executescript(SCHEMA)
    return _db


# typer main.py run create concert --help
@create_app.command("concert")
def create_concert_events(
        name: str,
        description: str,
        available_tickets: int,
        ticket_price: int,
        artist: list[str] = typer.Option([], help="Artist ID to book for this event (repeatable)"),
):
    db = get_db()
    try:
        check_sold_out_price(available_tickets, ticket_price)
        with db:
            (event_id,) = db.execute(
                "INSERT INTO concert_events (name, description, available_tickets, ticket_price) "
                "VALUES (?, ?, ?, ?) RETURNING id",
                (name, description, available_tickets, ticket_price),
            ).fetchone()
            for artist_id in artist:
                db.execute(
                    "INSERT INTO event_artists (event_id, artist_id) VALUES (?, ?)",
                    (event_id, artist_id),
                )
                check_artist_rules(db, artist_id)
    except (sqlite3.IntegrityError, ValueError) as e:
        typer.echo(f"could not create event: {e}", err=True)
        raise typer.Exit(1)
    typer.echo(f"created event {name} ({event_id})")


# typer main.py run create artist --help
@create_app.command("artist")
def create_artist(name: str, booking_contact: str):
    db = get_db()
    try:
        with db:
            (artist_id,) = db.execute(
                "INSERT INTO artists (name, booking_contact) VALUES (?, ?) RETURNING id",
                (name, booking_contact),
            ).fetchone()
    except sqlite3.IntegrityError as e:
        typer.echo(f"could not create artist: {e}", err=True)
        raise typer.Exit(1)
    typer.echo(f"created artist: {name} ({artist_id})")


# typer main.py run show concert
@show_app.command("concert")
def show_concert_events():
    db = get_db()
    events = db.execute(
        "SELECT id, name, description, available_tickets, ticket_price FROM concert_events ORDER BY name"
    ).fetchall()
    typer.echo("List of all concert events:")
    for event_id, name, description, available_tickets, ticket_price in events:
        artists = [
            row[0]
            for row in db.execute(
                "SELECT a.name FROM artists a JOIN event_artists ea ON ea.artist_id = a.id "
                "WHERE ea.event_id = ? ORDER BY a.name",
                (event_id,),
            )
        ]
        typer.echo(f"- {name} ({event_id})")
        typer.echo(f"    {description}")
        typer.echo(f"    tickets: {available_tickets} @ {ticket_price}")
        typer.echo(f"    artists: {', '.join(artists) or 'none'}")


# typer main.py run show artist
@show_app.command("artist")
def show_artists():
    db = get_db()
    typer.echo("List of all artists:")
    for artist_id, name, booking_contact in db.execute(
            "SELECT id, name, booking_contact FROM artists ORDER BY name"
    ):
        typer.echo(f"- {name} <{booking_contact}> ({artist_id})")


# typer main.py run update concert --help
@update_app.command("concert")
def update_concert_events(
        name: str,
        description: str,
        available_tickets: int,
        ticket_price: int,
        artist: list[str] = typer.Option([], help="Artist ID to book for this event (repeatable)"),
):
    db = get_db()
    try:
        check_sold_out_price(available_tickets, ticket_price)
        with db:
            (event_id,) = db.execute(
                "INSERT INTO concert_events (name, description, available_tickets, ticket_price) "
                "VALUES (?, ?, ?, ?) RETURNING id",
                (name, description, available_tickets, ticket_price),
            ).fetchone()
            for artist_id in artist:
                db.execute(
                    "INSERT INTO event_artists (event_id, artist_id) VALUES (?, ?)",
                    (event_id, artist_id),
                )
                check_artist_rules(db, artist_id)
    except (sqlite3.IntegrityError, ValueError) as e:
        typer.echo(f"could not create event: {e}", err=True)
        raise typer.Exit(1)
    typer.echo(f"created event {name} ({event_id})")


# typer main.py run update_ artist --help
@update_app.command("artist")
def update_artist(name: str, booking_contact: str):
    db = get_db()
    try:
        with db:
            (artist_id,) = db.execute(
                "INSERT INTO artists (name, booking_contact) VALUES (?, ?) RETURNING id",
                (name, booking_contact),
            ).fetchone()
    except sqlite3.IntegrityError as e:
        typer.echo(f"could not create artist: {e}", err=True)
        raise typer.Exit(1)
    typer.echo(f"created artist: {name} ({artist_id})")


# typer main.py run update concert --help
@delete_app.command("concert")
def delete_concert_events(
        name: str,
        description: str,
        available_tickets: int,
        ticket_price: int,
        artist: list[str] = typer.Option([], help="Artist ID to book for this event (repeatable)"),
):
    db = get_db()
    try:
        check_sold_out_price(available_tickets, ticket_price)
        with db:
            (event_id,) = db.execute(
                "INSERT INTO concert_events (name, description, available_tickets, ticket_price) "
                "VALUES (?, ?, ?, ?) RETURNING id",
                (name, description, available_tickets, ticket_price),
            ).fetchone()
            for artist_id in artist:
                db.execute(
                    "INSERT INTO event_artists (event_id, artist_id) VALUES (?, ?)",
                    (event_id, artist_id),
                )
                check_artist_rules(db, artist_id)
    except (sqlite3.IntegrityError, ValueError) as e:
        typer.echo(f"could not create event: {e}", err=True)
        raise typer.Exit(1)
    typer.echo(f"created event {name} ({event_id})")


# typer main.py run update_ artist --help
@delete_app.command("artist")
def delete_artist(name: str, booking_contact: str):
    db = get_db()
    try:
        with db:
            (artist_id,) = db.execute(
                "INSERT INTO artists (name, booking_contact) VALUES (?, ?) RETURNING id",
                (name, booking_contact),
            ).fetchone()
    except sqlite3.IntegrityError as e:
        typer.echo(f"could not create artist: {e}", err=True)
        raise typer.Exit(1)
    typer.echo(f"created artist: {name} ({artist_id})")



if __name__ == "__main__":
    app()
