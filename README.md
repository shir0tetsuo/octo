# OCTO

## Online Cartographer Tool/Observatory

**Project uses:** Python, Github Pages, jquery, HTML, CSS, Caddy (HTTPS Proxy)

to serve dynamically built web pages with a backend API server (for modularity so we can put the database itself on another machine) and a frontend API server (so we can communicate the data back to Github and handle "user authentication")

No API response? People will still know we exist, because the page is hosted on **Github Pages.**

Tired of fumbling with CSS for documentation? **Github Pages.**

Too much read/write overhead of the same HTML/CSS/JS files? **Github Pages!**

## Adding Zones

You will be required to change:

- static variables in `engine/databases.py`
- references to zones size in JS nav limiters
- pydantic references to literals

See 34d8ccf, f546c6f

### Why would we want to separate the database API from the frontend API?

Primarily because if the database is just a database, we can serve it over our network using a Raspberry Pi.
<img width="1696" height="779" alt="flow_diagram" src="https://github.com/user-attachments/assets/a17dd76c-fc84-4d18-8070-c94fa978ab2d" />

### Github Page &rarr; HTTPS API Frontend &rarr; Database Backend
Leverages dynamic page building with static Github Pages and jquery.

- Github Pages handles static (and "dynamic" jquery pages) distribution.
- Caddy serves a proxy with HTTPS Encryption magically.
- The frontend API handles "user authentication".
- The backend passes data to the frontend API then back to the end-user.

Things we can assume right now:
- Headers set on the page will be passed to the frontend server
    - If not, we can funnel it through jquery anyway with extra steps.
- It won't lag too badly, I hope.
- Github is resilient to becoming obsolete.

## How will we handle authentication?
The idea is fresh in my mind at the time of writing, we figure that there could be a bot that generates an API key, rate limited for safety of course.

## Okay, but __why__?
This project is intended to replace "Hybrid Ledgers", we are creating an infinite-plane address-based entity archive, storing a database of "psychic links" that others may contribute to.

## What is a "Psychic Link"?
Mental content. Information. A bookmark to a location, to an idea, to a Noun. How do you access this information? We provide a "map", you just have to follow it with your mind.

## Project Setup
(Python version 3.12.3)
(Caddy)

More information to come on hosting local instances.

> [!IMPORTANT]
> You should put your installation behind
> a Caddy server proxy, in this case, the
> server will serve HTTPS :443 at `octo.shadowsword.ca` by default,
> or by your local instance on :9300 for testing.

### Create start script `start_server.sh`

Your start script might look different depending on where you put your database server;
For simplicity, both are included here, useful for testing:

```bash
#!/usr/bin/env bash
export DB_X_API_KEY="THE_API_KEY_GENERATED_FROM_NEW_API_KEY_JUPYTER..."
export DB_SERVER="http://localhost:9401"
source ./venv/bin/activate
python3 db_server.py &
python3 fe_server.py
# Caddy start not covered here
wait
```

(Linux amd64) If you've put the Caddyfile in the root repository directory, `start_caddy.sh`:
```bash
#!/bin/bash
~/your_download_location/caddy_linux_amd64 run --config ~/Application/octo/Caddyfile
```

You may also set the following exports, this controls database cache IO settings:

```python
POOL_SIZE      = int(os.getenv("POOL_SIZE", 4))
FLUSH_INTERVAL = float(os.getenv("FLUSH_INTERVAL", 2.0))
MAX_QUEUE_ROWS = int(os.getenv("MAX_QUEUE_ROWS", 100)) # or 1000
LRU_CACHE_SIZE = int(os.getenv("LRU_CACHE_SIZE", 2048))
```

Don't forget to `chmod u+x ./start_*.sh`

### Caddyfile
Your Caddyfile should look something like this:
```
some.domain {

    @notApi {
        not path /api/*
    }

    respond @notApi 404

    reverse_proxy localhost:9300 {
        header_up Host {host}
        header_up X-Real-IP {remote_host}
    }
}
```
