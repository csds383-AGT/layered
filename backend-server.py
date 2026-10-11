from concurrent import futures
import logging
import os
import sys
from pathlib import Path

import grpc
from google.protobuf import empty_pb2

PROJECT_DIR = Path(__file__).resolve().parent
LOGIC_DIR = PROJECT_DIR / "logic"
if LOGIC_DIR.is_dir():
    sys.path.insert(0, str(LOGIC_DIR))

import services
import festhub_pb2 
import festhub_pb2_grpc 

PORT = int(os.getenv("BUSINESS_PORT", "50051"))

def field(record, name, default=None):
    """Read a field from a database namedtuple, object, or dictionary."""
    if isinstance(record, dict):
        return record.get(name, default)
    return getattr(record, name, default)


def string_id(value):
    return "" if value is None else str(value)


def to_concert(record):
    return festhub_pb2.Concert(
        id=string_id(field(record, "id")),
        name=field(record, "name", ""),
        description=field(record, "description", ""),
        available_tickets=field(record, "available_tickets", 0),
        # The services/repository layer stores prices as integer cents.
        ticket_price_cents=field(record, "ticket_price", field(record, "ticket_price_cents", 0)),
        artist_ids=[string_id(x) for x in (field(record, "artist_ids", []) or [])],
        category_ids=[string_id(x) for x in (field(record, "category_ids", []) or [])],
        media_ids=[string_id(x) for x in (field(record, "media_ids", []) or [])],
    )


def to_artist(record):
    return festhub_pb2.Artist(
        id=string_id(field(record, "id")),
        name=field(record, "name", ""),
        booking_contact=field(record, "booking_contact", ""),
        event_ids=[string_id(x) for x in (field(record, "event_ids", []) or [])],
    )


def to_category(record):
    return festhub_pb2.Category(
        id=string_id(field(record, "id")),
        name=field(record, "name", ""),
        description=field(record, "description", ""),
        event_ids=[string_id(x) for x in (field(record, "event_ids", []) or [])],
    )


def to_media(record):
    return festhub_pb2.Media(
        id=string_id(field(record, "id")),
        event_id=string_id(field(record, "event_id")),
        image_url=field(record, "image_url", ""),
    )


def abort_for_error(context, error):
    """Map known service errors to useful gRPC status codes.

    FestHubError is the application's business-rule exception. Unexpected exceptions
    are logged server-side and returned without leaking internal details.
    """
    message = str(error)
    lowered = message.lower()

    if isinstance(error, services.FestHubError):
        if lowered.startswith("no ") and " with id " in lowered:
            code = grpc.StatusCode.NOT_FOUND
        elif any(phrase in lowered for phrase in (
            "already exists", "already booked", "already in this category",
        )):
            code = grpc.StatusCode.ALREADY_EXISTS
        else:
            code = grpc.StatusCode.INVALID_ARGUMENT
        context.abort(code, message)

    if isinstance(error, (ValueError, TypeError)):
        context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)
    if isinstance(error, LookupError):
        context.abort(grpc.StatusCode.NOT_FOUND, message)

    logging.exception("Unhandled error in gRPC request", exc_info=(type(error), error, error.__traceback__))
    context.abort(grpc.StatusCode.INTERNAL, "Internal server error")


def invoke(context, function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except Exception as error:
        abort_for_error(context, error)


class FestHubService(festhub_pb2_grpc.FestHubServiceServicer):
    # Concerts
    def CreateConcert(self, request, context):
        result = invoke(
            context, services.create_concert,
            name=request.name,
            description=request.description,
            available_tickets=request.available_tickets,
            ticket_price=request.ticket_price,
            custom_id=request.custom_id or None,
            artist_ids=list(request.artist_ids),
            category_ids=list(request.category_ids),
            media_ids=list(request.media_ids),
        )
        return festhub_pb2.IdResponse(id=string_id(result))

    def ShowConcerts(self, request, context):
        records = invoke(context, services.find_concerts, request.id or None)
        return festhub_pb2.ShowConcertsResponse(concerts=[to_concert(x) for x in records])

    def UpdateConcert(self, request, context):
        invoke(
            context, services.update_concert,
            event_id=request.id,
            name=request.name if request.HasField("name") else None,
            description=request.description if request.HasField("description") else None,
            available_tickets=request.available_tickets if request.HasField("available_tickets") else None,
            ticket_price=request.ticket_price if request.HasField("ticket_price") else None,
            add_artist_ids=list(request.add_artist_ids),
            remove_artist_ids=list(request.remove_artist_ids),
            add_category_ids=list(request.add_category_ids),
            remove_category_ids=list(request.remove_category_ids),
            add_media_ids=list(request.add_media_ids),
            remove_media_ids=list(request.remove_media_ids),
        )
        return empty_pb2.Empty()

    def DeleteConcert(self, request, context):
        media_ids, category_ids = invoke(context, services.delete_concert, request.id)
        return festhub_pb2.DeleteConcertResponse(
            deleted_media_ids=[string_id(x) for x in media_ids],
            deleted_category_ids=[string_id(x) for x in category_ids],
        )

    # Artists
    def CreateArtist(self, request, context):
        result = invoke(
            context, services.create_artist,
            name=request.name,
            booking_contact=request.booking_contact,
            custom_id=request.custom_id or None,
            event_ids=list(request.event_ids),
        )
        return festhub_pb2.IdResponse(id=string_id(result))

    def ShowArtists(self, request, context):
        records = invoke(context, services.find_artists, request.id or None)
        return festhub_pb2.ShowArtistsResponse(artists=[to_artist(x) for x in records])

    def UpdateArtist(self, request, context):
        invoke(
            context, services.update_artist,
            artist_id=request.id,
            name=request.name if request.HasField("name") else None,
            booking_contact=request.booking_contact if request.HasField("booking_contact") else None,
            add_event_ids=list(request.add_event_ids),
            remove_event_ids=list(request.remove_event_ids),
        )
        return empty_pb2.Empty()

    def DeleteArtist(self, request, context):
        invoke(context, services.delete_artist, request.id)
        return empty_pb2.Empty()

    # Categories
    def CreateCategory(self, request, context):
        result = invoke(
            context, services.create_category,
            name=request.name,
            description=request.description,
            custom_id=request.custom_id or None,
            event_ids=list(request.event_ids),
        )
        return festhub_pb2.IdResponse(id=string_id(result))

    def ShowCategories(self, request, context):
        records = invoke(context, services.find_categories, request.id or None)
        return festhub_pb2.ShowCategoriesResponse(categories=[to_category(x) for x in records])

    def UpdateCategory(self, request, context):
        invoke(
            context, services.update_category,
            category_id=request.id,
            name=request.name if request.HasField("name") else None,
            description=request.description if request.HasField("description") else None,
            add_event_ids=list(request.add_event_ids),
            remove_event_ids=list(request.remove_event_ids),
        )
        return empty_pb2.Empty()

    def DeleteCategory(self, request, context):
        invoke(context, services.delete_category, request.id)
        return empty_pb2.Empty()

    # Media
    def CreateMedia(self, request, context):
        result = invoke(
            context, services.create_media,
            event_id=request.event_id,
            image_url=request.image_url,
            custom_id=request.custom_id or None,
        )
        return festhub_pb2.IdResponse(id=string_id(result))

    def ShowMedia(self, request, context):
        records = invoke(context, services.find_media, request.id or None)
        return festhub_pb2.ShowMediaResponse(media=[to_media(x) for x in records])

    def UpdateMedia(self, request, context):
        invoke(
            context, services.update_media,
            media_id=request.id,
            event_id=request.event_id if request.HasField("event_id") else None,
            image_url=request.image_url if request.HasField("image_url") else None,
        )
        return empty_pb2.Empty()

    def DeleteMedia(self, request, context):
        invoke(context, services.delete_media, request.id)
        return empty_pb2.Empty()


def serve():
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    # one worker, because every request shares repository's single database connection
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=1))
    festhub_pb2_grpc.add_FestHubServiceServicer_to_server(FestHubService(), server)
    bound_port = server.add_insecure_port(f"0.0.0.0:{PORT}")
    if bound_port == 0:
        raise RuntimeError(f"Could not bind gRPC server to port {PORT}")
    server.start()
    logging.info("FestHub gRPC server listening on port %s", PORT)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
