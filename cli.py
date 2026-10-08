import shlex
from contextlib import contextmanager

import typer

import services
from services import FestHubError

try:
    import readline  # arrow keys and command history in the shell (Windows has these built in)
except ImportError:
    pass

# ======================================================================
# Errors and output formatting
# ======================================================================

def fail(message):
    typer.echo(message, err=True)
    raise typer.Exit(1)


@contextmanager
def report_errors(action=None):
    try:
        yield
    except FestHubError as e:
        fail(f"could not {action}: {e}" if action else str(e))


def to_dollars(cents):
    return f"${cents / 100:,.2f}"


def format_ids(ids):
    return ", ".join(ids) if ids else "none"


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
    with report_errors("create event"):
        event_id = services.create_concert(name, description, available_tickets, ticket_price, custom_id,
                                           artist_ids=artist, category_ids=category, media_ids=media)
    typer.echo(f"created event {name} ({event_id})")


@show_app.command("concert", help="Show all concert events, or one by ID")
def show_concert_events(event_id: str | None = typer.Argument(None, help="Show only this event")):
    with report_errors():
        events = services.find_concerts(event_id)
    if not events:
        typer.echo("no concert events yet")
    for event in events:
        typer.echo(f"- {event.name} ({event.id})")
        typer.echo(f"    description: {event.description}")
        typer.echo(f"    available tickets: {event.available_tickets}")
        typer.echo(f"    ticket price: {to_dollars(event.ticket_price)}")
        typer.echo(f"    artist ids: {format_ids(event.artist_ids)}")
        typer.echo(f"    category ids: {format_ids(event.category_ids)}")
        typer.echo(f"    media ids: {format_ids(event.media_ids)}")


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
    with report_errors("update event"):
        services.update_concert(event_id, name, description, available_tickets, ticket_price,
                                add_artist_ids=add_artist, remove_artist_ids=remove_artist,
                                add_category_ids=add_category, remove_category_ids=remove_category,
                                add_media_ids=add_media, remove_media_ids=remove_media)
    typer.echo(f"updated event {event_id}")


@delete_app.command("concert", help="Delete a concert event")
def delete_concert_events(event_id: str):
    with report_errors("delete event"):
        deleted = services.delete_concert(event_id)
    typer.echo(f"deleted event {event_id}")
    for media_id in deleted.media_ids:
        typer.echo(f"    also deleted media {media_id}")
    for category_id in deleted.category_ids:
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
    with report_errors("create artist"):
        artist_id = services.create_artist(name, booking_contact, custom_id, event_ids=event)
    typer.echo(f"created artist {name} ({artist_id})")


@show_app.command("artist", help="Show all artists, or one by ID")
def show_artists(artist_id: str | None = typer.Argument(None, help="Show only this artist")):
    with report_errors():
        artists = services.find_artists(artist_id)
    if not artists:
        typer.echo("no artists yet")
    for artist in artists:
        typer.echo(f"- {artist.name} ({artist.id})")
        typer.echo(f"    booking contact: {artist.booking_contact}")
        typer.echo(f"    event ids: {format_ids(artist.event_ids)}")


@update_app.command("artist", help="Update an artist")
def update_artist(
        artist_id: str,
        name: str | None = typer.Option(None, help="New artist name"),
        booking_contact: str | None = typer.Option(None, help="New booking contact email"),
        add_event: list[str] = typer.Option([], help="Event ID to book this artist for (repeatable)"),
        remove_event: list[str] = typer.Option([], help="Event ID to unbook this artist from (repeatable)"),
):
    with report_errors("update artist"):
        services.update_artist(artist_id, name, booking_contact,
                               add_event_ids=add_event, remove_event_ids=remove_event)
    typer.echo(f"updated artist {artist_id}")


@delete_app.command("artist", help="Delete an artist")
def delete_artist(artist_id: str):
    with report_errors("delete artist"):
        services.delete_artist(artist_id)
    typer.echo(f"deleted artist {artist_id}")


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
    with report_errors("create category"):
        category_id = services.create_category(name, description, custom_id, event_ids=event)
    typer.echo(f"created category {name} ({category_id})")


@show_app.command("category", help="Show all categories, or one by ID")
def show_categories(category_id: str | None = typer.Argument(None, help="Show only this category")):
    with report_errors():
        categories = services.find_categories(category_id)
    if not categories:
        typer.echo("no categories yet")
    for category in categories:
        typer.echo(f"- {category.name} ({category.id})")
        typer.echo(f"    description: {category.description}")
        typer.echo(f"    event ids: {format_ids(category.event_ids)}")


@update_app.command("category", help="Update a category")
def update_category(
        category_id: str,
        name: str | None = typer.Option(None, help="New category name"),
        description: str | None = typer.Option(None, help="New category description"),
        add_event: list[str] = typer.Option([], help="Event ID to add to this category (repeatable)"),
        remove_event: list[str] = typer.Option([], help="Event ID to remove from this category (repeatable)"),
):
    with report_errors("update category"):
        services.update_category(category_id, name, description,
                                 add_event_ids=add_event, remove_event_ids=remove_event)
    typer.echo(f"updated category {category_id}")


@delete_app.command("category", help="Delete a category")
def delete_category(category_id: str):
    with report_errors("delete category"):
        services.delete_category(category_id)
    typer.echo(f"deleted category {category_id}")


# ======================================================================
# Media commands
# ======================================================================

@create_app.command("media", help="Create a promotional media asset")
def create_media(
        event_id: str,
        image_url: str,
        custom_id: str | None = typer.Option(None, "--id", help="Custom ID"),
):
    with report_errors("create media"):
        media_id = services.create_media(event_id, image_url, custom_id)
    typer.echo(f"created media {image_url} ({media_id})")


@show_app.command("media", help="Show all media, or one by ID")
def show_media(media_id: str | None = typer.Argument(None, help="Show only this media asset")):
    with report_errors():
        media_assets = services.find_media(media_id)
    if not media_assets:
        typer.echo("no media yet")
    for media in media_assets:
        typer.echo(f"- {media.image_url} ({media.id})")
        typer.echo(f"    event id: {media.event_id}")


@update_app.command("media", help="Update a media asset")
def update_media(
        media_id: str,
        event_id: str | None = typer.Option(None, help="New parent event ID"),
        image_url: str | None = typer.Option(None, help="New image URL"),
):
    with report_errors("update media"):
        services.update_media(media_id, event_id, image_url)
    typer.echo(f"updated media {media_id}")


@delete_app.command("media", help="Delete a media asset")
def delete_media(media_id: str):
    with report_errors("delete media"):
        services.delete_media(media_id)
    typer.echo(f"deleted media {media_id}")


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


# python cli.py shell
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
