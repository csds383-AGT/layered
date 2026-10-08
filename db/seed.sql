INSERT INTO concert_events (id, name, description, available_tickets, ticket_price)
VALUES (DEFAULT, 'Live at Grahams Garage', 'Bring a lawn chair', 40, 1000),
       ('eeeeeeee-0000-4000-8000-000000000001', 'Live at Aarons Basement', 'Thao on drums', 30, 500),
       ('eeeeeeee-0000-4000-8000-000000000002', 'CWRU Jammy Jam', 'CaseCash accepted', 200, 15000);

INSERT INTO artists (id, name, booking_contact)
VALUES ('aaaaaaaa-0000-4000-8000-000000000001', 'Graham Girone', 'graham@case.edu');

INSERT INTO event_artists (event_id, artist_id)
VALUES ('eeeeeeee-0000-4000-8000-000000000001', 'aaaaaaaa-0000-4000-8000-000000000001'),
       ('eeeeeeee-0000-4000-8000-000000000002', 'aaaaaaaa-0000-4000-8000-000000000001');

INSERT INTO categories (id, name, description)
VALUES ('cccccccc-0000-4000-8000-000000000001', 'Midterms Week', 'Midterms Week shows'),
       ('cccccccc-0000-4000-8000-000000000002', 'Finals Week', 'Exam Week shows'),
       ('cccccccc-0000-4000-8000-000000000003', 'Indie Summer', 'summahtime');

INSERT INTO event_categories (event_id, category_id)
VALUES ('eeeeeeee-0000-4000-8000-000000000002', 'cccccccc-0000-4000-8000-000000000001'),
       ('eeeeeeee-0000-4000-8000-000000000002', 'cccccccc-0000-4000-8000-000000000002'),
       ('eeeeeeee-0000-4000-8000-000000000001', 'cccccccc-0000-4000-8000-000000000003'),
       ('eeeeeeee-0000-4000-8000-000000000002', 'cccccccc-0000-4000-8000-000000000003');

INSERT INTO media (id, event_id, image_url)
VALUES ('dddddddd-0000-4000-8000-000000000001', 'eeeeeeee-0000-4000-8000-000000000002', 'https://picsum.photos'),
       ('dddddddd-0000-4000-8000-000000000002', 'eeeeeeee-0000-4000-8000-000000000002', 'https://example.com/poster-1.png'),
       ('dddddddd-0000-4000-8000-000000000003', 'eeeeeeee-0000-4000-8000-000000000002', 'https://example.com/poster-2.png');
