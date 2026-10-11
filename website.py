import os
from flask import Flask
from flask import render_template
import json

# Run with command flask --app website.py run --reload


app = Flask(__name__)
decoder = json.decoder.JSONDecoder()
buisness_ip = os.getenv("BUISNESS_IP")
buisness_port = os.getenv("BUISNESS_PORT")

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

@app.route("/concert")
def concert_page():
    # ask server for info
    raw_returns = "{}" # a really big list of concerts ig

    # Replace stuff here with the id's later
    sample_return = """
[
  {
    "id": "eeeeeeee-0000-4000-8000-000000000002",
    "name": "CWRU Jammy Jam",
    "description": "CaseCash accepted",
    "available_tickets": 200,
    "ticket_price": 15000,
    "artists": ["Kavin!!!"],
    "categories": ["Just Drums"],
    "media": ["Break Core 3"]
  },
  {
    "id": "eeeeeeee-0000-4000-8000-000000000003",
    "name": "CWRU Jammy Jam But better",
    "description": "CaseCash accepted",
    "available_tickets": 200,
    "ticket_price": 15000,
    "artists": ["Evil Kavin >:)"],
    "categories": ["Vocal"],
    "media": ["raw tunes"]
  }
]
"""
    reply = decoder.decode(sample_return)

    """ uncomment when these functions are real
    temp_artist = []
    for artist in reply[artist_ids]:
        temp_artist.append(get_artist(artist)) # calls middle layer
    reply[artists] = temp_artist

    temp_category = []
    for category in reply[category_ids]:
        temp_category.append(get_category(category)) # calls middle layer
    reply[categories] = temp_category

    temp_media = []
    for media in reply[media_ids]:
        temp_media.append(get_media(media)) # calls middle layer
    reply[media] = temp_media
    """
    # all of these better be strings so help me god

    # render page with the goods
    return render_template("concert.html", concerts=reply)

@app.route("/artist")
def artist_page():
    # ask server for info
    raw_returns = "{}" # a really big list of concerts ig

    # Replace stuff here with the id's later
    sample_return = """
    [
        {
        "id": "eeeeeeee-0000-4000-8000-000000000004",
        "name": "Kavin!!!",
        "booking_contact": "kavin@example.com",
        "event_ids": ["eeeeeeee-0000-4000-8000-000000000002"],
        "events": ["CWRU Jammy Jam"]
        },
        {
        "id": "eeeeeeee-0000-4000-8000-000000000005",
        "name": "Evil Kavin >:)",
        "booking_contact": "kavin@example.com",
        "event_ids": ["eeeeeeee-0000-4000-8000-000000000003"],
        "events": ["CWRU Jammy Jam But better"]
        }
    ]
    """

    reply = decoder.decode(sample_return)
    # all of these better be strings so help me god

    # render page with the goods
    return render_template("artist.html", artists=reply)

@app.route("/category")
def catagory_page():
    # ask server for info
    raw_returns = "{}" # a really big list of concerts ig

    # Replace stuff here with the id's later
    sample_return = """
[
  {
    "id": "eeeeeeee-0000-4000-8000-000000000001",
    "name": "Just Drums",
    "description": "High energy percussion-focused sets and solo drumming sessions",
    "event_ids": [
      "eeeeeeee-0000-4000-8000-000000000002"
    ]
  },
  {
    "id": "eeeeeeee-0000-4000-8000-000000000002",
    "name": "Vocal",
    "description": "A cappella, choral, and solo vocal performances",
    "event_ids": [
      "eeeeeeee-0000-4000-8000-000000000003"
    ]
  },
  {
    "id": "eeeeeeee-0000-4000-8000-000000000003",
    "name": "Electronic & Breakcore",
    "description": "Fast tempo synth, samples, and experimental beats",
    "event_ids": [
      "eeeeeeee-0000-4000-8000-000000000002",
      "eeeeeeee-0000-4000-8000-000000000003"
    ]
  }
]
"""

    reply = decoder.decode(sample_return)
    # all of these better be strings so help me god

    # render page with the goods
    return render_template("category.html", categories=reply)

@app.route("/media")
def media_page():
    # ask server for info
    raw_returns = "{}" # a really big list of concerts ig

    # Replace stuff here with the id's later
    sample_return = """
[
  {
    "id": "eeeeeeee-0000-4000-8000-000000000002",
    "image_url": "Break Core 3",
    "event_id": "eeeeeeee-0000-4000-8000-000000000002"
  },
  {
    "id": "eeeeeeee-0000-4000-8000-000000000003",
    "image_url": "raw tunes",
    "event_id": "eeeeeeee-0000-4000-8000-000000000003"
  }
]
"""

    reply = decoder.decode(sample_return)
    # all of these better be strings so help me god

    # render page with the goods
    return render_template("media.html", media_assets=reply)

# ======================================================================
# Api Segments
# These are here just to catch the create/update posts. Just passes data to Buisness end
# ======================================================================


@app.route("/api")
def api():
    return "Why are you here?"


# Concert
@app.route("/api/concert/create", methods=['POST'])
def create_concert():
    return "Success"

@app.route("/api/concert/update", methods=['POST'])
def update_concert():
    return "Success"

@app.route("/api/concert/delete", methods=['POST'])
def delete_concert():
    return "Success"

# Category
@app.route("/api/category/create", methods=['POST'])
def create_category():
    return "Success" 

@app.route("/api/category/update", methods=['POST'])
def update_category():
    return "Success"

@app.route("/api/category/delete", methods=['POST'])
def delete_category():
    return "Success"
# media
@app.route("/api/media/create", methods=['POST'])
def create_media():
    return "Success"

@app.route("/api/media/update", methods=['POST'])
def update_media():
    return "Success"

@app.route("/api/media/delete", methods=['POST'])
def delete_media():
    return "Success"