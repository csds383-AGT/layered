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
# 2: id, name, description, available_tickets (int), ticket_price (int in cents), artist_ids, category_ids, media_ids (lists of uuid strings)
# Artist: id, name, booking_contact, event_ids
# Category: id, name, description, event_ids
# Media: id, event_id, image_url 



# Api Structure: /api/{Catagory}/{Command}





@app.route("/")
def front_page():
    return render_template("frontpage.html")

@app.route("/concerts")
def concerts():
    # ask server for info
    raw_returns = "{}" # Some json file idk
    reply = decoder.decode(raw_returns)

    # render page with the goods
    return render_template("concerts.html", concerts=reply.concerts)




# ======================================================================
# Api Segments
# ======================================================================


@app.route("/api")
def api():
    return "Why are you here?"