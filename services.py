from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import UUID

from email_validator import EmailNotValidError, validate_email

import repository


class FestHubError(Exception):
    pass


# ======================================================================
# Input checks
# ======================================================================

def parse_id(custom_id):
    if custom_id is None:
        return None
    try:
        return str(UUID(custom_id))
    except ValueError:
        raise FestHubError("custom ID must be a valid UUID")


def to_cents(price):
    try:
        cents = Decimal(price) * 100
    except InvalidOperation:
        raise FestHubError(f"ticket price must be a decimal number like 25.50, got {price}")
    if not cents.is_finite() or cents != cents.to_integral_value():
        raise FestHubError(f"ticket price must be a decimal number with at most 2 decimal places, got {price}")
    return int(cents)


def is_url(value):
    try:
        parts = urlsplit(value)
    except ValueError:
        return False
    host = parts.hostname or ""
    has_spaces = any(character.isspace() for character in value)
    return parts.scheme in ("http", "https") and ("." in host or host == "localhost") and not has_spaces


# ======================================================================
# Business rules
# ======================================================================

def check_lengths(name, description=""):
    if len(name) > 2000:
        raise FestHubError("name must be 2000 characters or fewer")
    if len(description) > 10000:
        raise FestHubError("description must be 10000 characters or fewer")


def check_concert(event):
    check_lengths(event.name, event.description)
    if event.available_tickets < 0:
        raise FestHubError("available tickets cannot be negative")
    if event.ticket_price <= 0:
        raise FestHubError("ticket price must be more than 0")
    if event.available_tickets == 0 and event.ticket_price > 10_000:
        raise FestHubError("a sold out event (0 tickets) cannot cost more than $100.00")


def check_artist(artist):
    check_lengths(artist.name)
    try:
        validate_email(artist.booking_contact, check_deliverability=False)
    except EmailNotValidError:
        raise FestHubError("booking contact must be a valid email address")


def check_category(category):
    check_lengths(category.name, category.description)


def check_media(media):
    if not is_url(media.image_url):
        raise FestHubError("image URL must be a valid web address like https://example.com/poster.png")


def check_artist_rules(artist_id):
    summary = repository.artist_booking_summary(artist_id)
    if summary.duplicate_names:
        raise FestHubError(f"artist {artist_id} is already booked for an event with this name")
    if summary.total_price > 50_000_000:
        raise FestHubError(f"artist {artist_id}'s total ticket prices cannot exceed $500,000.00")


# ======================================================================
# Shared helpers
# ======================================================================

def require(table, record_id, label):
    record = repository.get(table, record_id)
    if record is None:
        raise FestHubError(f"no {label} with id {record_id}")
    return record


def find_records(table, record_id, label, order_by="name"):
    rows = repository.find(table, record_id, order_by)
    if record_id and not rows:
        raise FestHubError(f"no {label} with id {record_id}")
    return rows


def insert(table, custom_id, record, duplicate_message):
    record_id = repository.insert(table, custom_id, record)
    if record_id is None:
        raise FestHubError(duplicate_message)
    return record_id


def update(table, record_id, label, changes):
    record = repository.update(table, record_id, changes)
    if record is None:
        raise FestHubError(f"no {label} with id {record_id}")
    return record


def delete_record(table, record_id, label):
    with repository.transaction():
        if not repository.delete(table, record_id):
            raise FestHubError(f"no {label} with id {record_id}")


# ======================================================================
# Links between records
# ======================================================================

def book_artist(event_id, artist_id):
    require("concert_events", event_id, "event")
    require("artists", artist_id, "artist")
    if not repository.link("event_artists", event_id, artist_id):
        raise FestHubError("that artist is already booked for this event")


def unbook_artist(event_id, artist_id):
    if not repository.unlink("event_artists", "artist_id", event_id, artist_id):
        raise FestHubError(f"artist {artist_id} is not booked for event {event_id}")


def add_event_to_category(event_id, category_id):
    require("concert_events", event_id, "event")
    require("categories", category_id, "category")
    if not repository.link("event_categories", event_id, category_id):
        raise FestHubError("that event is already in this category")


def remove_event_from_category(event_id, category_id):
    if not repository.unlink("event_categories", "category_id", event_id, category_id):
        raise FestHubError(f"event {event_id} is not in category {category_id}")


def move_media_to_event(event_id, media_id):
    # a media asset has exactly one parent event, so this replaces its old one
    require("concert_events", event_id, "event")
    update("media", media_id, "media", SimpleNamespace(event_id=event_id))


def delete_media_from_event(event_id, media_id):
    # media cannot exist without a parent event, so taking it off its event deletes it
    if not repository.unlink("media", "id", event_id, media_id):
        raise FestHubError(f"media {media_id} is not attached to event {event_id}")


# ======================================================================
# Concert events
# ======================================================================

def create_concert(name, description, available_tickets, ticket_price, custom_id=None,
                   artist_ids=(), category_ids=(), media_ids=()):
    with repository.transaction():
        custom_id = parse_id(custom_id)
        event = SimpleNamespace(name=name, description=description, available_tickets=available_tickets,
                                ticket_price=to_cents(ticket_price))
        check_concert(event)
        event_id = insert("concert_events", custom_id, event, "an event with that ID already exists")
        for artist_id in artist_ids:
            book_artist(event_id, artist_id)
            check_artist_rules(artist_id)
        for category_id in category_ids:
            add_event_to_category(event_id, category_id)
        for media_id in media_ids:
            move_media_to_event(event_id, media_id)
        return event_id


def find_concerts(event_id=None):
    return find_records("concert_details", event_id, "event")


def update_concert(event_id, name=None, description=None, available_tickets=None, ticket_price=None,
                   add_artist_ids=(), remove_artist_ids=(), add_category_ids=(), remove_category_ids=(),
                   add_media_ids=(), remove_media_ids=()):
    with repository.transaction():
        cents = None if ticket_price is None else to_cents(ticket_price)
        changes = SimpleNamespace(name=name, description=description, available_tickets=available_tickets,
                                  ticket_price=cents)
        check_concert(update("concert_events", event_id, "event", changes))
        for change, linked_ids in [
            (book_artist, add_artist_ids),
            (unbook_artist, remove_artist_ids),
            (add_event_to_category, add_category_ids),
            (remove_event_from_category, remove_category_ids),
            (move_media_to_event, add_media_ids),
            (delete_media_from_event, remove_media_ids),
        ]:
            for linked_id in linked_ids:
                change(event_id, linked_id)
        # a new name or price can break the rules for any artist booked on this event
        for artist_id in require("concert_details", event_id, "event").artist_ids:
            check_artist_rules(artist_id)


def delete_concert(event_id):
    with repository.transaction():
        event = require("concert_details", event_id, "event")
        # the event's bookings, category links, and media are deleted with it (ON DELETE CASCADE)
        repository.delete("concert_events", event_id)
        # orphan cleanup: delete this event's categories if no other event uses them
        return event.media_ids, repository.delete_unused_categories(event.category_ids)


# ======================================================================
# Artists
# ======================================================================

def create_artist(name, booking_contact, custom_id=None, event_ids=()):
    with repository.transaction():
        custom_id = parse_id(custom_id)
        artist = SimpleNamespace(name=name, booking_contact=booking_contact)
        check_artist(artist)
        artist_id = insert("artists", custom_id, artist, "an artist with that ID already exists")
        for event_id in event_ids:
            book_artist(event_id, artist_id)
        check_artist_rules(artist_id)
        return artist_id


def find_artists(artist_id=None):
    return find_records("artist_details", artist_id, "artist")


def update_artist(artist_id, name=None, booking_contact=None, add_event_ids=(), remove_event_ids=()):
    with repository.transaction():
        changes = SimpleNamespace(name=name, booking_contact=booking_contact)
        check_artist(update("artists", artist_id, "artist", changes))
        for event_id in add_event_ids:
            book_artist(event_id, artist_id)
        for event_id in remove_event_ids:
            unbook_artist(event_id, artist_id)
        check_artist_rules(artist_id)


def delete_artist(artist_id):
    delete_record("artists", artist_id, "artist")


# ======================================================================
# Categories
# ======================================================================

def create_category(name, description, custom_id=None, event_ids=()):
    with repository.transaction():
        custom_id = parse_id(custom_id)
        category = SimpleNamespace(name=name, description=description)
        check_category(category)
        category_id = insert("categories", custom_id, category, "a category with that ID already exists")
        for event_id in event_ids:
            add_event_to_category(event_id, category_id)
        return category_id


def find_categories(category_id=None):
    return find_records("category_details", category_id, "category")


def update_category(category_id, name=None, description=None, add_event_ids=(), remove_event_ids=()):
    with repository.transaction():
        changes = SimpleNamespace(name=name, description=description)
        check_category(update("categories", category_id, "category", changes))
        for event_id in add_event_ids:
            add_event_to_category(event_id, category_id)
        for event_id in remove_event_ids:
            remove_event_from_category(event_id, category_id)


def delete_category(category_id):
    delete_record("categories", category_id, "category")


# ======================================================================
# Media
# ======================================================================

def create_media(event_id, image_url, custom_id=None):
    with repository.transaction():
        require("concert_events", event_id, "event")
        custom_id = parse_id(custom_id)
        media = SimpleNamespace(event_id=event_id, image_url=image_url)
        check_media(media)
        return insert("media", custom_id, media, "a media asset with that ID already exists")


def find_media(media_id=None):
    return find_records("media", media_id, "media", order_by="image_url")


def update_media(media_id, event_id=None, image_url=None):
    with repository.transaction():
        if event_id is not None:
            require("concert_events", event_id, "event")
        check_media(update("media", media_id, "media", SimpleNamespace(event_id=event_id, image_url=image_url)))


def delete_media(media_id):
    delete_record("media", media_id, "media")
