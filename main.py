import shlex
import sqlite3
import typer
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4
from email_validator import EmailNotValidError, validate_email

SCHEMA = """
         CREATE TABLE concert_events
         (
             id                TEXT PRIMARY KEY NOT NULL DEFAULT (new_uuid()),
             name              TEXT    NOT NULL CHECK (length(name) <= 2000),
             description       TEXT    NOT NULL CHECK (length(description) <= 10000),
             available_tickets INTEGER NOT NULL CHECK (available_tickets >= 0),
             ticket_price      INTEGER NOT NULL CHECK (ticket_price > 0), -- in cents (SQLite has no exact decimal type)
             CONSTRAINT sold_out_event_price_cannot_exceed_100 CHECK (available_tickets > 0 OR ticket_price <= 10000)
         );

         CREATE TABLE artists
         (
             id              TEXT PRIMARY KEY NOT NULL DEFAULT (new_uuid()),
             name            TEXT NOT NULL CHECK (length(name) <= 2000),
             booking_contact TEXT NOT NULL CHECK (is_email(booking_contact))
         );

         CREATE TABLE event_artists
         (
             event_id  TEXT NOT NULL REFERENCES concert_events (id) ON DELETE CASCADE,
             artist_id TEXT NOT NULL REFERENCES artists (id) ON DELETE CASCADE,
             PRIMARY KEY (event_id, artist_id)
         );
         """


def is_email(value):
    try:
        validate_email(value, check_deliverability=False)
        return True
    except EmailNotValidError:
        return False


db = sqlite3.connect(":memory:")
db.create_function("new_uuid", 0, lambda: str(uuid4()))
db.create_function("is_email", 1, is_email, deterministic=True)
db.execute("PRAGMA foreign_keys = ON")
db.executescript(SCHEMA)


def fail(message):
    typer.echo(message, err=True)
    raise typer.Exit(1)


def to_cents(price):
    try:
        cents = Decimal(price) * 100
    except InvalidOperation:
        raise ValueError(f"ticket price must be a decimal number like 25.50, got {price}")
    if not cents.is_finite() or cents != cents.to_integral_value():
        raise ValueError(f"ticket price must be a decimal number with at most 2 decimal places, got {price}")
    return int(cents)


def check_artist_rules(artist_id):
    duplicate_names, total_price = db.execute(
        "SELECT COUNT(*) - COUNT(DISTINCT e.name), SUM(e.ticket_price) "
        "FROM event_artists ea JOIN concert_events e ON e.id = ea.event_id WHERE ea.artist_id = ?",
        (artist_id,),
    ).fetchone()
    if duplicate_names:
        raise ValueError(f"artist {artist_id} is already booked for an event with this name")
    if (total_price or 0) > 50_000_000:
        raise ValueError(f"artist {artist_id}'s total ticket prices cannot exceed $500,000.00")


app = typer.Typer()
create_app = typer.Typer()
app.add_typer(create_app, name="create")
show_app = typer.Typer()
app.add_typer(show_app, name="show")
update_app = typer.Typer()
app.add_typer(update_app, name="update")
delete_app = typer.Typer()
app.add_typer(delete_app, name="delete")


@create_app.command("concert")
def create_concert_events(
        name: str,
        description: str,
        available_tickets: int,
        ticket_price: str = typer.Argument(help="Ticket price, e.g. 25.50"),
        custom_id: str | None = typer.Option(None, "--id", help="Custom UUID (generated if omitted)"),
        artist: list[str] = typer.Option([], help="Artist ID to book for this event (repeatable)"),
):
    try:
        custom_id = None if custom_id is None else str(UUID(custom_id))
        with db:
            # without --id the database generates one, and RETURNING gives back whichever id was used
            (event_id,) = db.execute(
                "INSERT INTO concert_events VALUES (COALESCE(?, new_uuid()), ?, ?, ?, ?) RETURNING id",
                (custom_id, name, description, available_tickets, to_cents(ticket_price)),
            ).fetchone()
            for artist_id in artist:
                db.execute("INSERT INTO event_artists VALUES (?, ?)", (event_id, artist_id))
                check_artist_rules(artist_id)
    except (sqlite3.IntegrityError, ValueError) as e:
        fail(f"could not create event: {e}")
    typer.echo(f"created event {name} ({event_id})")


@create_app.command("artist")
def create_artist(
        name: str,
        booking_contact: str,
        custom_id: str | None = typer.Option(None, "--id", help="Custom UUID (generated if omitted)"),
        event: list[str] = typer.Option([], help="Event ID to book this artist for (repeatable)"),
):
    try:
        custom_id = None if custom_id is None else str(UUID(custom_id))
        with db:
            (artist_id,) = db.execute(
                "INSERT INTO artists VALUES (COALESCE(?, new_uuid()), ?, ?) RETURNING id",
                (custom_id, name, booking_contact),
            ).fetchone()
            for event_id in event:
                db.execute("INSERT INTO event_artists VALUES (?, ?)", (event_id, artist_id))
            check_artist_rules(artist_id)
    except (sqlite3.IntegrityError, ValueError) as e:
        fail(f"could not create artist: {e}")
    typer.echo(f"created artist {name} ({artist_id})")


@show_app.command("concert")
def show_concert_events(event_id: str | None = typer.Argument(None, help="Show only this event")):
    # with no id (NULL) the WHERE matches every row
    events = db.execute(
        "SELECT * FROM concert_events WHERE ? IS NULL OR id = ? ORDER BY name", (event_id, event_id)
    ).fetchall()
    if event_id and not events:
        fail(f"no event with id {event_id}")
    for event_id, name, description, available_tickets, ticket_price in events:
        artist_ids = [row[0] for row in db.execute("SELECT artist_id FROM event_artists WHERE event_id = ?", (event_id,))]
        typer.echo(f"- {name} ({event_id})")
        typer.echo(f"    description: {description}")
        typer.echo(f"    available tickets: {available_tickets}")
        typer.echo(f"    ticket price: ${ticket_price / 100:,.2f}")
        typer.echo(f"    artist ids: {', '.join(artist_ids) or 'none'}")


@show_app.command("artist")
def show_artists(artist_id: str | None = typer.Argument(None, help="Show only this artist")):
    artists = db.execute(
        "SELECT * FROM artists WHERE ? IS NULL OR id = ? ORDER BY name", (artist_id, artist_id)
    ).fetchall()
    if artist_id and not artists:
        fail(f"no artist with id {artist_id}")
    for artist_id, name, booking_contact in artists:
        event_ids = [row[0] for row in db.execute("SELECT event_id FROM event_artists WHERE artist_id = ?", (artist_id,))]
        typer.echo(f"- {name} ({artist_id})")
        typer.echo(f"    booking contact: {booking_contact}")
        typer.echo(f"    event ids: {', '.join(event_ids) or 'none'}")


@update_app.command("concert")
def update_concert_events(
        event_id: str,
        name: str | None = typer.Option(None, help="New event name"),
        description: str | None = typer.Option(None, help="New event description"),
        available_tickets: int | None = typer.Option(None, help="New number of available tickets"),
        ticket_price: str | None = typer.Option(None, help="New ticket price, e.g. 25.50"),
        add_artist: list[str] = typer.Option([], help="Artist ID to book for this event (repeatable)"),
        remove_artist: list[str] = typer.Option([], help="Artist ID to unbook from this event (repeatable)"),
):
    try:
        cents = None if ticket_price is None else to_cents(ticket_price)
        with db:
            # options left out are None (NULL), so COALESCE keeps the column's current value
            updated = db.execute(
                "UPDATE concert_events SET name = COALESCE(?, name), description = COALESCE(?, description), "
                "available_tickets = COALESCE(?, available_tickets), ticket_price = COALESCE(?, ticket_price) "
                "WHERE id = ?",
                (name, description, available_tickets, cents, event_id),
            ).rowcount
            if not updated:
                raise ValueError(f"no event with id {event_id}")
            for artist_id in add_artist:
                db.execute("INSERT INTO event_artists VALUES (?, ?)", (event_id, artist_id))
            for artist_id in remove_artist:
                if not db.execute(
                        "DELETE FROM event_artists WHERE event_id = ? AND artist_id = ?", (event_id, artist_id)
                ).rowcount:
                    raise ValueError(f"artist {artist_id} is not booked for this event")
            # a new name or price can break the rules for any artist booked on this event
            for (artist_id,) in db.execute("SELECT artist_id FROM event_artists WHERE event_id = ?", (event_id,)).fetchall():
                check_artist_rules(artist_id)
    except (sqlite3.IntegrityError, ValueError) as e:
        fail(f"could not update event: {e}")
    typer.echo(f"updated event {event_id}")


@update_app.command("artist")
def update_artist(
        artist_id: str,
        name: str | None = typer.Option(None, help="New artist name"),
        booking_contact: str | None = typer.Option(None, help="New booking contact email"),
        add_event: list[str] = typer.Option([], help="Event ID to book this artist for (repeatable)"),
        remove_event: list[str] = typer.Option([], help="Event ID to unbook this artist from (repeatable)"),
):
    try:
        with db:
            updated = db.execute(
                "UPDATE artists SET name = COALESCE(?, name), booking_contact = COALESCE(?, booking_contact) "
                "WHERE id = ?",
                (name, booking_contact, artist_id),
            ).rowcount
            if not updated:
                raise ValueError(f"no artist with id {artist_id}")
            for event_id in add_event:
                db.execute("INSERT INTO event_artists VALUES (?, ?)", (event_id, artist_id))
            for event_id in remove_event:
                if not db.execute(
                        "DELETE FROM event_artists WHERE event_id = ? AND artist_id = ?", (event_id, artist_id)
                ).rowcount:
                    raise ValueError(f"artist is not booked for event {event_id}")
            check_artist_rules(artist_id)
    except (sqlite3.IntegrityError, ValueError) as e:
        fail(f"could not update artist: {e}")
    typer.echo(f"updated artist {artist_id}")


@delete_app.command("concert")
def delete_concert_events(event_id: str):
    with db:
        deleted = db.execute("DELETE FROM concert_events WHERE id = ?", (event_id,)).rowcount
    if not deleted:
        fail(f"could not delete event: no event with id {event_id}")
    typer.echo(f"deleted event {event_id}")


@delete_app.command("artist")
def delete_artist(artist_id: str):
    with db:
        deleted = db.execute("DELETE FROM artists WHERE id = ?", (artist_id,)).rowcount
    if not deleted:
        fail(f"could not delete artist: no artist with id {artist_id}")
    typer.echo(f"deleted artist {artist_id}")


# typer main.py run shell
@app.command("shell")
def shell():
    while True:
        line = input("festhub> ")
        if line.strip() == "exit":
            break
        try:
            app(shlex.split(line))
        except SystemExit:
            pass


if __name__ == "__main__":
    app()
