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
