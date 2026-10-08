from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit
from uuid import UUID

from email_validator import EmailNotValidError, validate_email

import repository

# ======================================================================
# Errors
# ======================================================================

class FestHubError(Exception):
    pass


class NotFound(FestHubError):
    pass


class InvalidInput(FestHubError):
    pass


class Conflict(FestHubError):
    pass


# ======================================================================
# Records returned to the presentation layer
# ======================================================================

@dataclass
class Concert:
    id: str
    name: str
    description: str
    available_tickets: int
    ticket_price: int  # in cents
    artist_ids: list[str]
    category_ids: list[str]
    media_ids: list[str]


@dataclass
class Artist:
    id: str
    name: str
    booking_contact: str
    event_ids: list[str]


@dataclass
class Category:
    id: str
    name: str
    description: str
    event_ids: list[str]


@dataclass
class Media:
    id: str
    event_id: str
    image_url: str


@dataclass
class DeletedConcert:
    media_ids: list[str]
    category_ids: list[str]


# ======================================================================
# Input checks
# ======================================================================

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


def parse_id(custom_id):
    if custom_id is None:
        return None
    try:
        return str(UUID(custom_id))
    except ValueError:
        raise InvalidInput("custom ID must be a valid UUID")


def to_cents(price):
    try:
        cents = Decimal(price) * 100
    except InvalidOperation:
        raise InvalidInput(f"ticket price must be a decimal number like 25.50, got {price}")
    if not cents.is_finite() or cents != cents.to_integral_value():
        raise InvalidInput(f"ticket price must be a decimal number with at most 2 decimal places, got {price}")
    return int(cents)


def or_current(new_value, current_value):
    # options left out are None, so the record keeps its current value
    return current_value if new_value is None else new_value


# ======================================================================
# Business rules
# ======================================================================

def check_name(name):
    if len(name) > 2000:
        raise InvalidInput("name must be 2000 characters or fewer")


def check_description(description):
    if len(description) > 10000:
        raise InvalidInput("description must be 10000 characters or fewer")


def check_concert(name, description, available_tickets, ticket_price):
    check_name(name)
    check_description(description)
    if available_tickets < 0:
        raise InvalidInput("available tickets cannot be negative")
    if ticket_price <= 0:
        raise InvalidInput("ticket price must be more than 0")
    if available_tickets == 0 and ticket_price > 10_000:
        raise InvalidInput("a sold out event (0 tickets) cannot cost more than $100.00")


def check_artist(name, booking_contact):
    check_name(name)
    if not is_email(booking_contact):
        raise InvalidInput("booking contact must be a valid email address")


def check_image_url(image_url):
    if not is_url(image_url):
        raise InvalidInput("image URL must be a valid web address like https://example.com/poster.png")


def check_artist_rules(artist_id):
    duplicate_names, total_price = repository.artist_booking_summary(artist_id)
    if duplicate_names:
        raise Conflict(f"artist {artist_id} is already booked for an event with this name")
    if total_price > 50_000_000:
        raise InvalidInput(f"artist {artist_id}'s total ticket prices cannot exceed $500,000.00")


def require(table, record_id, label):
    if not repository.exists(table, record_id):
        raise NotFound(f"no {label} with id {record_id}")


def require_unused_id(table, custom_id, message):
    if custom_id is not None and repository.exists(table, custom_id):
        raise Conflict(message)


# ======================================================================
# Links between records
# ======================================================================

def book_artist(event_id, artist_id):
    require("concert_events", event_id, "event")
    require("artists", artist_id, "artist")
    if repository.is_booked(event_id, artist_id):
        raise Conflict("that artist is already booked for this event")
    repository.book_artist(event_id, artist_id)


def unbook_artist(event_id, artist_id):
    if not repository.unbook_artist(event_id, artist_id):
        raise NotFound(f"artist {artist_id} is not booked for event {event_id}")


def add_event_to_category(event_id, category_id):
    require("concert_events", event_id, "event")
    require("categories", category_id, "category")
    if repository.is_in_category(event_id, category_id):
        raise Conflict("that event is already in this category")
    repository.add_event_to_category(event_id, category_id)


def remove_event_from_category(event_id, category_id):
    if not repository.remove_event_from_category(event_id, category_id):
        raise NotFound(f"event {event_id} is not in category {category_id}")


def move_media_to_event(media_id, event_id):
    # a media asset has exactly one parent event, so this replaces its old one
    require("concert_events", event_id, "event")
    if not repository.move_media(media_id, event_id):
        raise NotFound(f"no media with id {media_id}")


def delete_media_from_event(media_id, event_id):
    # media cannot exist without a parent event, so taking it off its event deletes it
    if not repository.delete_media_from_event(media_id, event_id):
        raise NotFound(f"media {media_id} is not attached to event {event_id}")


# ======================================================================
# Shared lookups
# ======================================================================

def find_records(table, record_id, label, order_by="name"):
    rows = repository.find(table, record_id, order_by)
    if record_id and not rows:
        raise NotFound(f"no {label} with id {record_id}")
    return rows


def delete_record(table, record_id, label):
    with repository.transaction():
        if not repository.delete(table, record_id):
            raise NotFound(f"no {label} with id {record_id}")


# ======================================================================
# Concert events
# ======================================================================

def create_concert(name, description, available_tickets, ticket_price, custom_id=None,
                   artist_ids=(), category_ids=(), media_ids=()):
    with repository.transaction():
        custom_id = parse_id(custom_id)
        cents = to_cents(ticket_price)
        check_concert(name, description, available_tickets, cents)
        require_unused_id("concert_events", custom_id, "an event with that ID already exists")
        event_id = repository.insert_concert(custom_id, name, description, available_tickets, cents)
        for artist_id in artist_ids:
            book_artist(event_id, artist_id)
            check_artist_rules(artist_id)
        for category_id in category_ids:
            add_event_to_category(event_id, category_id)
        for media_id in media_ids:
            move_media_to_event(media_id, event_id)
    return event_id


def find_concerts(event_id=None):
    return [
        Concert(**row,
                artist_ids=repository.artist_ids_for_event(row["id"]),
                category_ids=repository.category_ids_for_event(row["id"]),
                media_ids=repository.media_ids_for_event(row["id"]))
        for row in find_records("concert_events", event_id, "event")
    ]


def update_concert(event_id, name=None, description=None, available_tickets=None, ticket_price=None,
                   add_artist_ids=(), remove_artist_ids=(), add_category_ids=(), remove_category_ids=(),
                   add_media_ids=(), remove_media_ids=()):
    with repository.transaction():
        cents = None if ticket_price is None else to_cents(ticket_price)
        event = repository.get("concert_events", event_id)
        if event is None:
            raise NotFound(f"no event with id {event_id}")
        name = or_current(name, event["name"])
        description = or_current(description, event["description"])
        available_tickets = or_current(available_tickets, event["available_tickets"])
        cents = or_current(cents, event["ticket_price"])
        check_concert(name, description, available_tickets, cents)
        repository.update_concert(event_id, name, description, available_tickets, cents)
        for artist_id in add_artist_ids:
            book_artist(event_id, artist_id)
        for artist_id in remove_artist_ids:
            unbook_artist(event_id, artist_id)
        for category_id in add_category_ids:
            add_event_to_category(event_id, category_id)
        for category_id in remove_category_ids:
            remove_event_from_category(event_id, category_id)
        for media_id in add_media_ids:
            move_media_to_event(media_id, event_id)
        for media_id in remove_media_ids:
            delete_media_from_event(media_id, event_id)
        # a new name or price can break the rules for any artist booked on this event
        for artist_id in repository.artist_ids_for_event(event_id):
            check_artist_rules(artist_id)


def delete_concert(event_id):
    with repository.transaction():
        require("concert_events", event_id, "event")
        category_ids = repository.category_ids_for_event(event_id)
        media_ids = repository.media_ids_for_event(event_id)
        # the event's bookings, category links, and media are deleted with it (ON DELETE CASCADE)
        repository.delete("concert_events", event_id)
        # orphan cleanup: delete this event's categories if no other event uses them
        unused_category_ids = []
        for category_id in category_ids:
            if not repository.category_in_use(category_id):
                repository.delete("categories", category_id)
                unused_category_ids.append(category_id)
    return DeletedConcert(media_ids, unused_category_ids)


# ======================================================================
# Artists
# ======================================================================

def create_artist(name, booking_contact, custom_id=None, event_ids=()):
    with repository.transaction():
        custom_id = parse_id(custom_id)
        check_artist(name, booking_contact)
        require_unused_id("artists", custom_id, "an artist with that ID already exists")
        artist_id = repository.insert_artist(custom_id, name, booking_contact)
        for event_id in event_ids:
            book_artist(event_id, artist_id)
        check_artist_rules(artist_id)
    return artist_id


def find_artists(artist_id=None):
    return [
        Artist(**row, event_ids=repository.event_ids_for_artist(row["id"]))
        for row in find_records("artists", artist_id, "artist")
    ]


def update_artist(artist_id, name=None, booking_contact=None, add_event_ids=(), remove_event_ids=()):
    with repository.transaction():
        artist = repository.get("artists", artist_id)
        if artist is None:
            raise NotFound(f"no artist with id {artist_id}")
        name = or_current(name, artist["name"])
        booking_contact = or_current(booking_contact, artist["booking_contact"])
        check_artist(name, booking_contact)
        repository.update_artist(artist_id, name, booking_contact)
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
        check_name(name)
        check_description(description)
        require_unused_id("categories", custom_id, "a category with that ID already exists")
        category_id = repository.insert_category(custom_id, name, description)
        for event_id in event_ids:
            add_event_to_category(event_id, category_id)
    return category_id


def find_categories(category_id=None):
    return [
        Category(**row, event_ids=repository.event_ids_for_category(row["id"]))
        for row in find_records("categories", category_id, "category")
    ]


def update_category(category_id, name=None, description=None, add_event_ids=(), remove_event_ids=()):
    with repository.transaction():
        category = repository.get("categories", category_id)
        if category is None:
            raise NotFound(f"no category with id {category_id}")
        name = or_current(name, category["name"])
        description = or_current(description, category["description"])
        check_name(name)
        check_description(description)
        repository.update_category(category_id, name, description)
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
        check_image_url(image_url)
        require_unused_id("media", custom_id, "a media asset with that ID already exists")
        media_id = repository.insert_media(custom_id, event_id, image_url)
    return media_id


def find_media(media_id=None):
    return [Media(**row) for row in find_records("media", media_id, "media", order_by="image_url")]


def update_media(media_id, event_id=None, image_url=None):
    with repository.transaction():
        if event_id is not None:
            require("concert_events", event_id, "event")
        media = repository.get("media", media_id)
        if media is None:
            raise NotFound(f"no media with id {media_id}")
        event_id = or_current(event_id, media["event_id"])
        image_url = or_current(image_url, media["image_url"])
        check_image_url(image_url)
        repository.update_media(media_id, event_id, image_url)


def delete_media(media_id):
    delete_record("media", media_id, "media")
