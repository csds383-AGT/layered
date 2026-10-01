import shlex
import sqlite3
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import typer
from email_validator import EmailNotValidError, validate_email

try:
    import readline  # arrow keys and command history in the shell (Windows has these built in)
except ImportError:
    pass

# ======================================================================
# Database
# ======================================================================

SCHEMA = """
         CREATE TABLE concert_events
         (
             id                TEXT PRIMARY KEY NOT NULL DEFAULT (new_uuid()),
             name              TEXT             NOT NULL CHECK (length(name) <= 2000),
             description       TEXT             NOT NULL CHECK (length(description) <= 10000),
             available_tickets INTEGER          NOT NULL CHECK (available_tickets >= 0),
             ticket_price      INTEGER          NOT NULL CHECK (ticket_price > 0),
             CONSTRAINT sold_out_event_price_cannot_exceed_100 CHECK (available_tickets > 0 OR ticket_price <= 10000)
         );

         CREATE TABLE artists
         (
             id              TEXT PRIMARY KEY NOT NULL DEFAULT (new_uuid()),
             name            TEXT             NOT NULL CHECK (length(name) <= 2000),
             booking_contact TEXT             NOT NULL CHECK (is_email(booking_contact))
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
             name        TEXT             NOT NULL CHECK (length(name) <= 2000),
             description TEXT             NOT NULL CHECK (length(description) <= 10000)
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
             image_url TEXT             NOT NULL CHECK (is_url(image_url))
         );
         """


def is_email(value):
    try:
        validate_email(value, check_deliverability=False)
        return True
    except EmailNotValidError:
        return False


def is_url(value):
    try:
        parts = urlsplit(value)
    except ValueError:
        return False
    host = parts.hostname or ""
    has_spaces = any(character.isspace() for character in value)
    return parts.scheme in ("http", "https") and ("." in host or host == "localhost") and not has_spaces


db = sqlite3.connect(":memory:")
db.row_factory = sqlite3.Row  # lets rows be read by column name like row["id"]
db.create_function("new_uuid", 0, lambda: str(uuid4()))
db.create_function("is_email", 1, is_email, deterministic=True)
db.create_function("is_url", 1, is_url, deterministic=True)
db.execute("PRAGMA foreign_keys = ON")
db.executescript(SCHEMA)

# ======================================================================
# Errors and input checks
# ======================================================================

READABLE_ERRORS = {
    "CHECK constraint failed: is_email(booking_contact)": "booking contact must be a valid email address",
    "CHECK constraint failed: length(name) <= 2000": "name must be 2000 characters or fewer",
    "CHECK constraint failed: length(description) <= 10000": "description must be 10000 characters or fewer",
    "CHECK constraint failed: available_tickets >= 0": "available tickets cannot be negative",
    "CHECK constraint failed: ticket_price > 0": "ticket price must be more than 0",
    "CHECK constraint failed: sold_out_event_price_cannot_exceed_100": "a sold out event (0 tickets) cannot cost more than $100.00",
    "UNIQUE constraint failed: concert_events.id": "an event with that ID already exists",
    "UNIQUE constraint failed: artists.id": "an artist with that ID already exists",
    "UNIQUE constraint failed: event_artists.event_id, event_artists.artist_id": "that artist is already booked for this event",
    "CHECK constraint failed: is_url(image_url)": "image URL must be a valid web address like https://example.com/poster.png",
    "UNIQUE constraint failed: categories.id": "a category with that ID already exists",
    "UNIQUE constraint failed: event_categories.event_id, event_categories.category_id": "that event is already in this category",
    "UNIQUE constraint failed: media.id": "a media asset with that ID already exists",
    "FOREIGN KEY constraint failed": "one of the linked IDs does not exist",
    "badly formed hexadecimal UUID string": "custom ID must be a valid UUID",
}


def fail(message):
    for error, readable in READABLE_ERRORS.items():
        message = message.replace(error, readable)
    typer.echo(message, err=True)
    raise typer.Exit(1)


def parse_id(custom_id):
    return None if custom_id is None else str(UUID(custom_id))


def to_cents(price):
    try:
        cents = Decimal(price) * 100
    except InvalidOperation:
        raise ValueError(f"ticket price must be a decimal number like 25.50, got {price}")
    if not cents.is_finite() or cents != cents.to_integral_value():
        raise ValueError(f"ticket price must be a decimal number with at most 2 decimal places, got {price}")
    return int(cents)


# ======================================================================
# Output formatting
# ======================================================================

def to_dollars(cents):
    return f"${cents / 100:,.2f}"


def format_ids(ids):
    return ", ".join(ids) if ids else "none"


# ======================================================================
# Database helpers
# ======================================================================

@contextmanager
def transaction(action):
    # runs the block as one transaction, so any error undoes the whole command
    try:
        with db:
            yield
    except (sqlite3.IntegrityError, ValueError) as e:
        fail(f"could not {action}: {e}")


def require(table, record_id, label):
    if db.execute(f"SELECT 1 FROM {table} WHERE id = ?", [record_id]).fetchone() is None:
        raise ValueError(f"no {label} with id {record_id}")


def find_records(table, record_id, label, order_by="name"):
    rows = db.execute(
        f"SELECT * FROM {table} WHERE ? IS NULL OR id = ? ORDER BY {order_by}", [record_id, record_id]
    ).fetchall()
    if record_id and not rows:
        fail(f"no {label} with id {record_id}")
    if not rows:
        typer.echo(f"no {table.replace('_', ' ')} yet")
    return rows


def delete_record(table, record_id, label):
    with db:
        record_found = db.execute(f"DELETE FROM {table} WHERE id = ?", [record_id]).rowcount > 0
    if not record_found:
        fail(f"could not delete {label}: no {label} with id {record_id}")
    typer.echo(f"deleted {label} {record_id}")


def book_artist(event_id, artist_id):
    require("concert_events", event_id, "event")
    require("artists", artist_id, "artist")
    db.execute("INSERT INTO event_artists VALUES (?, ?)", [event_id, artist_id])


def unbook_artist(event_id, artist_id):
    was_booked = db.execute("DELETE FROM event_artists WHERE event_id = ? AND artist_id = ?",
                            [event_id, artist_id]).rowcount > 0
    if not was_booked:
        raise ValueError(f"artist {artist_id} is not booked for event {event_id}")


def add_event_to_category(event_id, category_id):
    require("concert_events", event_id, "event")
    require("categories", category_id, "category")
    db.execute("INSERT INTO event_categories VALUES (?, ?)", [event_id, category_id])


def remove_event_from_category(event_id, category_id):
    was_in_category = db.execute("DELETE FROM event_categories WHERE event_id = ? AND category_id = ?",
                                 [event_id, category_id]).rowcount > 0
    if not was_in_category:
        raise ValueError(f"event {event_id} is not in category {category_id}")


def move_media_to_event(media_id, event_id):
    # a media asset has exactly one parent event, so this replaces its old one
    require("concert_events", event_id, "event")
    media_found = db.execute("UPDATE media SET event_id = ? WHERE id = ?", [event_id, media_id]).rowcount > 0
    if not media_found:
        raise ValueError(f"no media with id {media_id}")


def delete_media_from_event(media_id, event_id):
    # media cannot exist without a parent event, so taking it off its event deletes it
    was_attached = db.execute("DELETE FROM media WHERE id = ? AND event_id = ?",
                              [media_id, event_id]).rowcount > 0
    if not was_attached:
        raise ValueError(f"media {media_id} is not attached to event {event_id}")


# ======================================================================
# Business rules
# ======================================================================

def check_artist_rules(artist_id):
    duplicate_names, total_price = db.execute(
        "SELECT COUNT(*) - COUNT(DISTINCT e.name), SUM(e.ticket_price) "
        "FROM event_artists ea JOIN concert_events e ON e.id = ea.event_id WHERE ea.artist_id = ?",
        [artist_id],
    ).fetchone()
    if duplicate_names:
        raise ValueError(f"artist {artist_id} is already booked for an event with this name")
    if (total_price or 0) > 50_000_000:
        raise ValueError(f"artist {artist_id}'s total ticket prices cannot exceed $500,000.00")


# ======================================================================
# Typer command groups
# ======================================================================

app = typer.Typer(add_completion=False)
create_app = typer.Typer()
app.add_typer(create_app, name="create")
show_app = typer.Typer()
app.add_typer(show_app, name="show")
update_app = typer.Typer()
app.add_typer(update_app, name="update")
delete_app = typer.Typer()
app.add_typer(delete_app, name="delete")


# ======================================================================
# Concert event commands
# ======================================================================

@create_app.command("concert", help="Create a concert event")
def create_concert_events(
        name: str,
        description: str,
        available_tickets: int,
        ticket_price: str = typer.Argument(help="Ticket price, e.g. 25.50"),
        custom_id: str | None = typer.Option(None, "--id", help="Custom ID"),
        artist: list[str] = typer.Option([], help="Artist ID to book for this event (repeatable)"),
        category: list[str] = typer.Option([], help="Category ID to add this event to (repeatable)"),
        media: list[str] = typer.Option([], help="Media ID to move to this event (repeatable)"),
):
    with transaction("create event"):
        # without --id the database generates one, and RETURNING gives back whichever id was used
        event_id = db.execute(
            "INSERT INTO concert_events VALUES (COALESCE(?, new_uuid()), ?, ?, ?, ?) RETURNING id",
            [parse_id(custom_id), name, description, available_tickets, to_cents(ticket_price)],
        ).fetchone()["id"]
        for artist_id in artist:
            book_artist(event_id, artist_id)
            check_artist_rules(artist_id)
        for category_id in category:
            add_event_to_category(event_id, category_id)
        for media_id in media:
            move_media_to_event(media_id, event_id)
    typer.echo(f"created event {name} ({event_id})")


@show_app.command("concert", help="Show all concert events, or one by ID")
def show_concert_events(event_id: str | None = typer.Argument(None, help="Show only this event")):
    events = find_records("concert_events", event_id, "event")
    for event_id, name, description, available_tickets, ticket_price in events:
        artist_rows = db.execute("SELECT artist_id FROM event_artists WHERE event_id = ?", [event_id])
        artist_ids = [row["artist_id"] for row in artist_rows]
        category_rows = db.execute("SELECT category_id FROM event_categories WHERE event_id = ?", [event_id])
        category_ids = [row["category_id"] for row in category_rows]
        media_rows = db.execute("SELECT id FROM media WHERE event_id = ?", [event_id])
        media_ids = [row["id"] for row in media_rows]
        typer.echo(f"- {name} ({event_id})")
        typer.echo(f"    description: {description}")
        typer.echo(f"    available tickets: {available_tickets}")
        typer.echo(f"    ticket price: {to_dollars(ticket_price)}")
        typer.echo(f"    artist ids: {format_ids(artist_ids)}")
        typer.echo(f"    category ids: {format_ids(category_ids)}")
        typer.echo(f"    media ids: {format_ids(media_ids)}")


@update_app.command("concert", help="Update a concert event")
def update_concert_events(
        event_id: str,
        name: str | None = typer.Option(None, help="New event name"),
        description: str | None = typer.Option(None, help="New event description"),
        available_tickets: int | None = typer.Option(None, help="New number of available tickets"),
        ticket_price: str | None = typer.Option(None, help="New ticket price, e.g. 25.50"),
        add_artist: list[str] = typer.Option([], help="Artist ID to book for this event (repeatable)"),
        remove_artist: list[str] = typer.Option([], help="Artist ID to unbook from this event (repeatable)"),
        add_category: list[str] = typer.Option([], help="Category ID to add this event to (repeatable)"),
        remove_category: list[str] = typer.Option([], help="Category ID to remove this event from (repeatable)"),
        add_media: list[str] = typer.Option([], help="Media ID to move to this event (repeatable)"),
        remove_media: list[str] = typer.Option([], help="Media ID to delete from this event (repeatable)"),
):
    with transaction("update event"):
        cents = None if ticket_price is None else to_cents(ticket_price)
        # options left out are None (NULL), so COALESCE keeps the column's current value
        event_found = db.execute(
            "UPDATE concert_events SET name = COALESCE(?, name), description = COALESCE(?, description), "
            "available_tickets = COALESCE(?, available_tickets), ticket_price = COALESCE(?, ticket_price) "
            "WHERE id = ?",
            [name, description, available_tickets, cents, event_id],
        ).rowcount > 0
        if not event_found:
            raise ValueError(f"no event with id {event_id}")
        for artist_id in add_artist:
            book_artist(event_id, artist_id)
        for artist_id in remove_artist:
            unbook_artist(event_id, artist_id)
        for category_id in add_category:
            add_event_to_category(event_id, category_id)
        for category_id in remove_category:
            remove_event_from_category(event_id, category_id)
        for media_id in add_media:
            move_media_to_event(media_id, event_id)
        for media_id in remove_media:
            delete_media_from_event(media_id, event_id)
        # a new name or price can break the rules for any artist booked on this event
        booked = db.execute("SELECT artist_id FROM event_artists WHERE event_id = ?", [event_id]).fetchall()
        for row in booked:
            check_artist_rules(row["artist_id"])
    typer.echo(f"updated event {event_id}")


@delete_app.command("concert", help="Delete a concert event")
def delete_concert_events(event_id: str):
    with transaction("delete event"):
        require("concert_events", event_id, "event")
        category_rows = db.execute("SELECT category_id FROM event_categories WHERE event_id = ?", [event_id])
        category_ids = [row["category_id"] for row in category_rows]
        media_rows = db.execute("SELECT id FROM media WHERE event_id = ?", [event_id])
        media_ids = [row["id"] for row in media_rows]
        # the event's bookings, category links, and media are deleted with it (ON DELETE CASCADE)
        db.execute("DELETE FROM concert_events WHERE id = ?", [event_id])
        # orphan cleanup: delete this event's categories if no other event uses them
        unused_category_ids = []
        for category_id in category_ids:
            still_used = db.execute("SELECT 1 FROM event_categories WHERE category_id = ?", [category_id]).fetchone()
            if not still_used:
                db.execute("DELETE FROM categories WHERE id = ?", [category_id])
                unused_category_ids.append(category_id)
    typer.echo(f"deleted event {event_id}")
    for media_id in media_ids:
        typer.echo(f"    also deleted media {media_id}")
    for category_id in unused_category_ids:
        typer.echo(f"    also deleted category {category_id} (no events left)")


# ======================================================================
# Artist commands
# ======================================================================

@create_app.command("artist", help="Create an artist")
def create_artist(
        name: str,
        booking_contact: str,
        custom_id: str | None = typer.Option(None, "--id", help="Custom ID"),
        event: list[str] = typer.Option([], help="Event ID to book this artist for (repeatable)"),
):
    with transaction("create artist"):
        artist_id = db.execute(
            "INSERT INTO artists VALUES (COALESCE(?, new_uuid()), ?, ?) RETURNING id",
            [parse_id(custom_id), name, booking_contact],
        ).fetchone()["id"]
        for event_id in event:
            book_artist(event_id, artist_id)
        check_artist_rules(artist_id)
    typer.echo(f"created artist {name} ({artist_id})")


@show_app.command("artist", help="Show all artists, or one by ID")
def show_artists(artist_id: str | None = typer.Argument(None, help="Show only this artist")):
    artists = find_records("artists", artist_id, "artist")
    for artist_id, name, booking_contact in artists:
        event_rows = db.execute("SELECT event_id FROM event_artists WHERE artist_id = ?", [artist_id])
        event_ids = [row["event_id"] for row in event_rows]
        typer.echo(f"- {name} ({artist_id})")
        typer.echo(f"    booking contact: {booking_contact}")
        typer.echo(f"    event ids: {format_ids(event_ids)}")


@update_app.command("artist", help="Update an artist")
def update_artist(
        artist_id: str,
        name: str | None = typer.Option(None, help="New artist name"),
        booking_contact: str | None = typer.Option(None, help="New booking contact email"),
        add_event: list[str] = typer.Option([], help="Event ID to book this artist for (repeatable)"),
        remove_event: list[str] = typer.Option([], help="Event ID to unbook this artist from (repeatable)"),
):
    with transaction("update artist"):
        artist_found = db.execute(
            "UPDATE artists SET name = COALESCE(?, name), booking_contact = COALESCE(?, booking_contact) "
            "WHERE id = ?",
            [name, booking_contact, artist_id],
        ).rowcount > 0
        if not artist_found:
            raise ValueError(f"no artist with id {artist_id}")
        for event_id in add_event:
            book_artist(event_id, artist_id)
        for event_id in remove_event:
            unbook_artist(event_id, artist_id)
        check_artist_rules(artist_id)
    typer.echo(f"updated artist {artist_id}")


@delete_app.command("artist", help="Delete an artist")
def delete_artist(artist_id: str):
    delete_record("artists", artist_id, "artist")


# ======================================================================
# Category commands
# ======================================================================

@create_app.command("category", help="Create a festival booking category")
def create_category(
        name: str,
        description: str,
        custom_id: str | None = typer.Option(None, "--id", help="Custom ID"),
        event: list[str] = typer.Option([], help="Event ID to add to this category (repeatable)"),
):
    with transaction("create category"):
        category_id = db.execute(
            "INSERT INTO categories VALUES (COALESCE(?, new_uuid()), ?, ?) RETURNING id",
            [parse_id(custom_id), name, description],
        ).fetchone()["id"]
        for event_id in event:
            add_event_to_category(event_id, category_id)
    typer.echo(f"created category {name} ({category_id})")


@show_app.command("category", help="Show all categories, or one by ID")
def show_categories(category_id: str | None = typer.Argument(None, help="Show only this category")):
    categories = find_records("categories", category_id, "category")
    for category_id, name, description in categories:
        event_rows = db.execute("SELECT event_id FROM event_categories WHERE category_id = ?", [category_id])
        event_ids = [row["event_id"] for row in event_rows]
        typer.echo(f"- {name} ({category_id})")
        typer.echo(f"    description: {description}")
        typer.echo(f"    event ids: {format_ids(event_ids)}")


@update_app.command("category", help="Update a category")
def update_category(
        category_id: str,
        name: str | None = typer.Option(None, help="New category name"),
        description: str | None = typer.Option(None, help="New category description"),
        add_event: list[str] = typer.Option([], help="Event ID to add to this category (repeatable)"),
        remove_event: list[str] = typer.Option([], help="Event ID to remove from this category (repeatable)"),
):
    with transaction("update category"):
        category_found = db.execute(
            "UPDATE categories SET name = COALESCE(?, name), description = COALESCE(?, description) WHERE id = ?",
            [name, description, category_id],
        ).rowcount > 0
        if not category_found:
            raise ValueError(f"no category with id {category_id}")
        for event_id in add_event:
            add_event_to_category(event_id, category_id)
        for event_id in remove_event:
            remove_event_from_category(event_id, category_id)
    typer.echo(f"updated category {category_id}")


@delete_app.command("category", help="Delete a category")
def delete_category(category_id: str):
    delete_record("categories", category_id, "category")


# ======================================================================
# Media commands
# ======================================================================

@create_app.command("media", help="Create a promotional media asset")
def create_media(
        event_id: str,
        image_url: str,
        custom_id: str | None = typer.Option(None, "--id", help="Custom ID"),
):
    with transaction("create media"):
        require("concert_events", event_id, "event")
        media_id = db.execute(
            "INSERT INTO media VALUES (COALESCE(?, new_uuid()), ?, ?) RETURNING id",
            [parse_id(custom_id), event_id, image_url],
        ).fetchone()["id"]
    typer.echo(f"created media {image_url} ({media_id})")


@show_app.command("media", help="Show all media, or one by ID")
def show_media(media_id: str | None = typer.Argument(None, help="Show only this media asset")):
    media_assets = find_records("media", media_id, "media", order_by="image_url")
    for media_id, event_id, image_url in media_assets:
        typer.echo(f"- {image_url} ({media_id})")
        typer.echo(f"    event id: {event_id}")


@update_app.command("media", help="Update a media asset")
def update_media(
        media_id: str,
        event_id: str | None = typer.Option(None, help="New parent event ID"),
        image_url: str | None = typer.Option(None, help="New image URL"),
):
    with transaction("update media"):
        if event_id is not None:
            require("concert_events", event_id, "event")
        media_found = db.execute(
            "UPDATE media SET event_id = COALESCE(?, event_id), image_url = COALESCE(?, image_url) WHERE id = ?",
            [event_id, image_url, media_id],
        ).rowcount > 0
        if not media_found:
            raise ValueError(f"no media with id {media_id}")
    typer.echo(f"updated media {media_id}")


@delete_app.command("media", help="Delete a media asset")
def delete_media(media_id: str):
    delete_record("media", media_id, "media")


# ======================================================================
# Interactive shell
# ======================================================================

def show_commands():
    typer.echo("Commands:")
    for group in app.registered_groups:
        for command in group.typer_instance.registered_commands:
            name = f"{group.name} {command.name}"
            typer.echo(f"  {name.ljust(18)}{command.help}")


def run_command(line):
    try:
        args = shlex.split(line)
    except ValueError as e:
        typer.echo(f"could not read command: {str(e).lower()}", err=True)
        return
    if args == ["help"]:
        show_commands()
        return
    if args and args[0] == "help":
        args = args[1:] + ["--help"]
    if args and args[0] == "shell":
        typer.echo("You're already in the shell.")
        return
    try:
        app(args, prog_name="")
    except SystemExit:
        pass


# typer main.py run shell
@app.command("shell", help="Start an interactive session", hidden=True)
def shell():
    typer.echo("FestHub - Team AGT (Aaron, Graham, Thao)")
    run_command("help")
    typer.echo("Examples:")
    typer.echo('  create concert "Live at Aaron\'s Basement" "Thao on drums" 30 5.00')
    typer.echo("  show concert")
    typer.echo('  update concert <event-id> --name "Live at Graham\'s Garage"')
    typer.echo("  delete concert <event-id>")
    typer.echo("Type help <command> for details, or exit to quit.")
    while True:
        line = input("festhub> ")
        if line.strip() == "exit":
            break
        run_command(line)


if __name__ == "__main__":
    app()
