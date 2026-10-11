import os
from flask import Flask, abort, jsonify, render_template, request
import json
import grpc
import festhub_pb2
import festhub_pb2_grpc
from decimal import Decimal, InvalidOperation
import logging

# Run with command flask --app website.py run --reload

app = Flask(__name__)
GRPC_TARGET = f"{os.getenv('BUSINESS_HOST', 'localhost')}:{os.getenv('BUSINESS_PORT', '50051')}"
channel = grpc.insecure_channel(GRPC_TARGET) # use insecure channel for development, switch to TLS for production
backend = festhub_pb2_grpc.FestHubServiceStub(channel)
RPC_TIMEOUT_SECONDS = float(os.getenv("GRPC_TIMEOUT_SECONDS", "3"))

def rpc(method, payload):
    """Call an RPC with a deadline and translate gRPC failures for HTTP clients."""
    try:
        return getattr(backend, method)(payload, timeout=RPC_TIMEOUT_SECONDS)
    except grpc.RpcError as error:
        code = error.code()
        message = error.details() or "The backend request failed."
        status = {
            grpc.StatusCode.INVALID_ARGUMENT: 400,
            grpc.StatusCode.NOT_FOUND: 404,
            grpc.StatusCode.ALREADY_EXISTS: 409,
            grpc.StatusCode.FAILED_PRECONDITION: 409,
            grpc.StatusCode.UNAVAILABLE: 503,
            grpc.StatusCode.DEADLINE_EXCEEDED: 504,
        }.get(code, 502)
        logging.warning("gRPC call %s failed (%s): %s", method, code.name, message)
        abort(status, description=message)


def parse_ids(value):
    """Accept either a list or a comma-separated string from the templates."""
    if value is None or value == "":
        return []
    if isinstance(value, list):
        values = value
    else:
        values = str(value).split(",")
    return [str(item).strip() for item in values if str(item).strip()]


def get_json():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, description="Expected a JSON object in the request body.")
    return data


def required(data, key):
    value = data.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        abort(400, description=f"Missing required field: {key}")
    return value


def price_to_decimal(value):
    """Templates submit prices in cents; the services layer accepts dollars."""
    if value is None or value == "":
        abort(400, description="Missing required field: ticket_price")
    try:
        cents = Decimal(str(value))
        if not cents.is_finite() or cents != cents.to_integral_value():
            raise InvalidOperation
        return format(cents / Decimal(100), ".2f")
    except (InvalidOperation, ValueError):
        abort(400, description="ticket_price must be an integer number of cents.")


def optional_price_to_decimal(data, key="ticket_price"):
    return price_to_decimal(data[key]) if key in data and data[key] is not None and data[key] != "" else None


def api_action(fn):
    """Keep API errors in the JSON shape the existing frontend expects."""
    try:
        result = fn()
        return jsonify(result or {"ok": True})
    except Exception as error:
        from werkzeug.exceptions import HTTPException
        if isinstance(error, HTTPException):
            return jsonify(message=error.description), error.code
        if isinstance(error, (ValueError, TypeError, InvalidOperation)):
            return jsonify(message=f"Invalid request value: {error}"), 400
        logging.exception("Unhandled web/API error")
        return jsonify(message="Internal server error"), 500

# required components
# Create Show Update Delete

# expected data formats
# Concert: id, name, description, available_tickets (int), ticket_price (int in cents), artist_ids, category_ids, media_ids (lists of uuid strings)
# Artist: id, name, booking_contact, event_ids
# Category: id, name, description, event_ids
# Media: id, event_id, image_url 



# Api Structure: /api/{Catagory}/{Command}





@app.route("/")
def front_page():
    return render_template("frontpage.html")

def fetch_concerts(concert_id=""):
    response = rpc("ShowConcerts", festhub_pb2.ShowConcertsRequest(id=concert_id))
    return list(response.concerts)


def fetch_artists():
    response = rpc("ShowArtists", festhub_pb2.ShowArtistsRequest())
    return [{
        "id": x.id, "name": x.name, "booking_contact": x.booking_contact,
        "event_ids": list(x.event_ids),
    } for x in response.artists]


def fetch_categories():
    response = rpc("ShowCategories", festhub_pb2.ShowCategoriesRequest())
    return [{
        "id": x.id, "name": x.name, "description": x.description,
        "event_ids": list(x.event_ids),
    } for x in response.categories]


def fetch_media(concerts):
    event_names = {c.id: c.name for c in concerts}
    response = rpc("ShowMedia", festhub_pb2.ShowMediaRequest())
    return [{
        "id": x.id, "event_id": x.event_id, "image_url": x.image_url,
        "name": x.image_url,
        "event_name": event_names.get(x.event_id, x.event_id),
    } for x in response.media]


def linked(ids, lookup):
    """Turn linked ids into {id, name} pairs; unknown ids fall back to the raw id."""
    return [{"id": i, "name": lookup[i]["name"] if i in lookup else i} for i in ids]


def concert_view(item, lookups):
    """Shape a concert for the templates: names for display, ids for form values."""
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "available_tickets": item.available_tickets,
        "ticket_price": item.ticket_price_cents,
        "artists": linked(item.artist_ids, lookups["artists"]),
        "categories": linked(item.category_ids, lookups["categories"]),
        "media": linked(item.media_ids, lookups["media"]),
        "artist_ids": list(item.artist_ids),
        "category_ids": list(item.category_ids),
        "media_ids": list(item.media_ids),
    }


def render_concert_page(title, concert_id=None):
    """Create and update share one template; update passes the concert so the form can be prefilled."""
    concerts = fetch_concerts()
    catalog = {
        "artists": fetch_artists(),
        "categories": fetch_categories(),
        "media": fetch_media(concerts),
    }
    lookups = {kind: {x["id"]: x for x in items} for kind, items in catalog.items()}

    current = None
    if concert_id is not None:
        current = next((c for c in concerts if c.id == concert_id), None)
        if current is None:
            abort(404, description=f"Concert not found: {concert_id}")

    return render_template(
        "concert.html",
        title=title,
        mode="update" if concert_id is not None else "create",
        concert=concert_view(current, lookups) if current is not None else None,
        concerts=[concert_view(c, lookups) for c in concerts],
        artist_catalog=catalog["artists"],
        category_catalog=catalog["categories"],
        media_catalog=catalog["media"],
    )


@app.route("/concert")
def concert_page():
    return render_concert_page("Create concert")


@app.route("/concert/<concert_id>/edit")
def edit_concert_page(concert_id):
    return render_concert_page("Update concert", concert_id)


@app.route("/artist")
def artist_page():
    return render_template("artist.html", artists=fetch_artists())


@app.route("/category")
def category_page():
    return render_template("category.html", categories=fetch_categories())


@app.route("/media")
def media_page():
    return render_template("media.html", media_assets=fetch_media(fetch_concerts()))


@app.route("/api")
def api_index():
    return jsonify(message="Use the /api/{resource}/{create|update|delete} endpoints."), 200


# Concert API
@app.post("/api/concert/create")
def create_concert():
    def action():
        data = get_json()
        response = rpc("CreateConcert", festhub_pb2.CreateConcertRequest(
            name=str(required(data, "name")),
            description=str(data.get("description") or ""),
            available_tickets=int(required(data, "available_tickets")),
            ticket_price=price_to_decimal(required(data, "ticket_price")),
            custom_id=str(data.get("custom_id") or ""),
            artist_ids=parse_ids(data.get("artist", data.get("artist_ids"))),
            category_ids=parse_ids(data.get("category", data.get("category_ids"))),
            media_ids=parse_ids(data.get("media", data.get("media_ids"))),
        ))
        return {"ok": True, "id": response.id}
    return api_action(action)


def apply_link_changes(payload, data, current, name):
    """Fill the add/remove ids for artist, category or media on an UpdateConcertRequest.

    Either the full desired list under `name` / `name_ids` (same keys create uses) is
    diffed against the concert's current links, or explicit `add_<name>` / `remove_<name>` lists are used.
    """
    desired = data.get(name, data.get(f"{name}_ids"))
    if desired is not None:
        wanted = parse_ids(desired)
        existing = list(getattr(current, f"{name}_ids"))
        added = [i for i in wanted if i not in existing]
        removed = [i for i in existing if i not in wanted]
    else:
        added = parse_ids(data.get(f"add_{name}", data.get(f"add_{name}_ids")))
        removed = parse_ids(data.get(f"remove_{name}", data.get(f"remove_{name}_ids")))
    getattr(payload, f"add_{name}_ids").extend(added)
    getattr(payload, f"remove_{name}_ids").extend(removed)


@app.post("/api/concert/update")
def update_concert():
    def action():
        data = get_json()
        concert_id = str(required(data, "event_id"))
        current = next((c for c in fetch_concerts(concert_id) if c.id == concert_id), None)
        if current is None:
            abort(404, description=f"Concert not found: {concert_id}")

        payload = festhub_pb2.UpdateConcertRequest(id=concert_id)
        if data.get("name") is not None:
            payload.name = str(data["name"])
        if data.get("description") is not None:
            payload.description = str(data["description"])
        if data.get("available_tickets") is not None:
            payload.available_tickets = int(data["available_tickets"])
        price = optional_price_to_decimal(data)
        if price is not None:
            payload.ticket_price = price
        for name in ("artist", "category", "media"):
            apply_link_changes(payload, data, current, name)
        rpc("UpdateConcert", payload)
        return {"ok": True}
    return api_action(action)


@app.post("/api/concert/delete")
def delete_concert():
    def action():
        data = get_json()
        response = rpc("DeleteConcert", festhub_pb2.DeleteConcertRequest(id=str(required(data, "event_id"))))
        return {"ok": True, "deleted_media_ids": list(response.deleted_media_ids),
                "deleted_category_ids": list(response.deleted_category_ids)}
    return api_action(action)


# Artist API
@app.post("/api/artist/create")
def create_artist():
    def action():
        data = get_json()
        response = rpc("CreateArtist", festhub_pb2.CreateArtistRequest(
            name=str(required(data, "name")),
            booking_contact=str(required(data, "booking_contact")),
            custom_id=str(data.get("custom_id") or ""),
            event_ids=parse_ids(data.get("event", data.get("event_ids"))),
        ))
        return {"ok": True, "id": response.id}
    return api_action(action)


@app.post("/api/artist/update")
def update_artist():
    def action():
        data = get_json()
        payload = festhub_pb2.UpdateArtistRequest(id=str(required(data, "artist_id")))
        if data.get("name") is not None:
            payload.name = str(data["name"])
        if data.get("booking_contact") is not None:
            payload.booking_contact = str(data["booking_contact"])
        payload.add_event_ids.extend(parse_ids(data.get("add_event", data.get("add_event_ids"))))
        payload.remove_event_ids.extend(parse_ids(data.get("remove_event", data.get("remove_event_ids"))))
        rpc("UpdateArtist", payload)
        return {"ok": True}
    return api_action(action)


@app.post("/api/artist/delete")
def delete_artist():
    def action():
        data = get_json()
        rpc("DeleteArtist", festhub_pb2.DeleteArtistRequest(id=str(required(data, "artist_id"))))
        return {"ok": True}
    return api_action(action)


# Category API
@app.post("/api/category/create")
def create_category():
    def action():
        data = get_json()
        response = rpc("CreateCategory", festhub_pb2.CreateCategoryRequest(
            name=str(required(data, "name")),
            description=str(data.get("description") or ""),
            custom_id=str(data.get("custom_id") or ""),
            event_ids=parse_ids(data.get("event", data.get("event_ids"))),
        ))
        return {"ok": True, "id": response.id}
    return api_action(action)


@app.post("/api/category/update")
def update_category():
    def action():
        data = get_json()
        payload = festhub_pb2.UpdateCategoryRequest(id=str(required(data, "category_id")))
        if data.get("name") is not None:
            payload.name = str(data["name"])
        if data.get("description") is not None:
            payload.description = str(data["description"])
        payload.add_event_ids.extend(parse_ids(data.get("add_event", data.get("add_event_ids"))))
        payload.remove_event_ids.extend(parse_ids(data.get("remove_event", data.get("remove_event_ids"))))
        rpc("UpdateCategory", payload)
        return {"ok": True}
    return api_action(action)


@app.post("/api/category/delete")
def delete_category():
    def action():
        data = get_json()
        rpc("DeleteCategory", festhub_pb2.DeleteCategoryRequest(id=str(required(data, "category_id"))))
        return {"ok": True}
    return api_action(action)


# Media API
@app.post("/api/media/create")
def create_media():
    def action():
        data = get_json()
        response = rpc("CreateMedia", festhub_pb2.CreateMediaRequest(
            event_id=str(required(data, "event_id")),
            image_url=str(required(data, "image_url")),
            custom_id=str(data.get("custom_id") or ""),
        ))
        return {"ok": True, "id": response.id}
    return api_action(action)


@app.post("/api/media/update")
def update_media():
    def action():
        data = get_json()
        payload = festhub_pb2.UpdateMediaRequest(id=str(required(data, "media_id")))
        if data.get("event_id") is not None:
            payload.event_id = str(data["event_id"])
        if data.get("image_url") is not None:
            payload.image_url = str(data["image_url"])
        rpc("UpdateMedia", payload)
        return {"ok": True}
    return api_action(action)


@app.post("/api/media/delete")
def delete_media():
    def action():
        data = get_json()
        rpc("DeleteMedia", festhub_pb2.DeleteMediaRequest(id=str(required(data, "media_id"))))
        return {"ok": True}
    return api_action(action)


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
