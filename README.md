# FestHub

1. install [docker desktop](https://www.docker.com/products/docker-desktop/) and open it
2. start the database
   ```bash
   docker compose up -d
   ```
3. install the python packages (first time only, needs python 3.10 or newer)
   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```
4. start the shell
   ```bash
   .venv/bin/python cli.py shell
   ```
5. type `exit` to leave the shell, then stop the database
   ```bash
   docker compose down
   ```

your data is kept between runs. to start over with an empty database, use `docker compose down -v` instead. do this once whenever `db/schema.sql` changes too.

on windows, use `.venv\Scripts\` instead of `.venv/bin/`.

if you want to access the postgres database  in your ide, use this config: ![img.png](img.png)
