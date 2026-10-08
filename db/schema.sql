CREATE TABLE concert_events
(
    id                UUID PRIMARY KEY DEFAULT uuidv7(),
    available_tickets BIGINT           NOT NULL,
    ticket_price      BIGINT           NOT NULL,
    name              TEXT             NOT NULL,
    description       TEXT             NOT NULL
);

CREATE TABLE artists
(
    id              UUID PRIMARY KEY DEFAULT uuidv7(),
    name            TEXT             NOT NULL,
    booking_contact TEXT             NOT NULL
);

CREATE TABLE event_artists
(
    event_id  UUID NOT NULL REFERENCES concert_events (id) ON DELETE CASCADE,
    artist_id UUID NOT NULL REFERENCES artists (id) ON DELETE CASCADE,
    PRIMARY KEY (event_id, artist_id)
);

CREATE TABLE categories
(
    id          UUID PRIMARY KEY DEFAULT uuidv7(),
    name        TEXT             NOT NULL,
    description TEXT             NOT NULL
);

CREATE TABLE event_categories
(
    event_id    UUID NOT NULL REFERENCES concert_events (id) ON DELETE CASCADE,
    category_id UUID NOT NULL REFERENCES categories (id) ON DELETE CASCADE,
    PRIMARY KEY (event_id, category_id)
);

CREATE TABLE media
(
    id        UUID PRIMARY KEY DEFAULT uuidv7(),
    event_id  UUID             NOT NULL REFERENCES concert_events (id) ON DELETE CASCADE,
    image_url TEXT             NOT NULL
);

CREATE VIEW concert_details AS
SELECT e.*,
       ARRAY(SELECT artist_id FROM event_artists WHERE event_id = e.id ORDER BY artist_id)       AS artist_ids,
       ARRAY(SELECT category_id FROM event_categories WHERE event_id = e.id ORDER BY category_id) AS category_ids,
       ARRAY(SELECT id FROM media WHERE event_id = e.id ORDER BY id)                            AS media_ids
FROM concert_events e;

CREATE VIEW artist_details AS
SELECT a.*, ARRAY(SELECT event_id FROM event_artists WHERE artist_id = a.id ORDER BY event_id) AS event_ids
FROM artists a;

CREATE VIEW category_details AS
SELECT c.*, ARRAY(SELECT event_id FROM event_categories WHERE category_id = c.id ORDER BY event_id) AS event_ids
FROM categories c;
