# FestHub

1. install [docker desktop](https://www.docker.com/products/docker-desktop/) and open it
2. start everything
   ```bash
   docker compose up --build --watch
   ```
3. open http://localhost:5001
4. press ctrl+c to stop

while it's running, saved changes to `website.py`, `templates/`, `backend-server.py`, and `logic/` show up on their own, and changes to `festhub.proto` or `requirements.txt` rebuild the containers.

to reset the database to the demo data (needed whenever `db/schema.sql` or `db/seed.sql` changes):

```bash
docker compose down -v
```

if you want to access the postgres database  in your ide, use this config: ![img.png](img.png)
