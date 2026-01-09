# OCTO

## Online Cartographer Tool/Observatory

<img width="1170" height="642" alt="image" src="https://github.com/user-attachments/assets/fc19f0a0-e2fd-44a4-bf14-a2df080fa4f5" />

**Project uses:** Python, Github Pages, jquery, HTML, CSS, Caddy (HTTPS Proxy)

to serve dynamically built web pages with a backend API server (for modularity so we can put the database itself on another machine) and a frontend API server (so we can communicate the data back to Github and handle "user authentication")

No API response? People will still know we exist, because the page is hosted on **Github Pages.**

Tired of fumbling with CSS for documentation? **Github Pages.**

Too much read/write overhead of the same HTML/CSS/JS files? **Github Pages!**

# Foreword

This project is transparent. You may always check for database statistics in the console in the status page,
or identify which version of the project is being used for the frontend and backend servers. All of our
source code is freely readable.

<img width="482" height="857" alt="image" src="https://github.com/user-attachments/assets/78deedab-07d7-406d-80f7-0b8f98f576d7" />

(Server runtime version is displayed on the bottom of the index card)

# How to Login

Use `/create_api_key` using the bot, it will generate an API Key for you using the server's AES256 encryption scheme.

Embedded in this data is your Discord User ID & a permission level. The default is 1.

Login to the site and enter your API Key (X-API-Key). Your account expires in 365 days if not renewed. Once you lose access to your account, your Site ID is not recoverable without administrator intervention.
Losing your Site ID will make it impossible to edit an existing iteration or stack on top of an existing "Entity" under your previous Site ID.

<img width="482" height="455" alt="image" src="https://github.com/user-attachments/assets/46d4f76c-bad1-47e0-9b54-d7448a5f2a2c" />
<img width="482" height="455" alt="image" src="https://github.com/user-attachments/assets/d90d4b27-8180-4229-b68a-199f25d4ff3a" />

# How to Use this application

Using the hosting power of [Github Pages](https://shir0tetsuo.github.io/octo), we use ajax requests to reach the frontend.

<img width="489" height="874" alt="Screenshot from 2026-01-07 00-07-18" src="https://github.com/user-attachments/assets/26d41173-c741-42bf-8a2d-8589dc6a1790" />

Each final glyph in a cell sequence is special, there is a link embed to the "Entity"

<img width="243" height="144" alt="Screenshot from 2026-01-06 19-22-07" src="https://github.com/user-attachments/assets/b6e6ca4b-12f1-4a4f-87b1-dab192c7ad10" />

Each "Entity" may contain an infinite stack of iterations. First you must claim ownership of that entity.

<img width="416" height="80" alt="Screenshot from 2026-01-06 19-23-12" src="https://github.com/user-attachments/assets/b0cd3af6-c768-4381-a86d-56d090a0f354" />

Use the coin icon displayed under the first glyph to **Mint** the "Genesis #0" iteration. Note that you may not edit a "Genesis #0" iteration.

<img width="114" height="195" alt="Screenshot from 2026-01-06 19-22-29" src="https://github.com/user-attachments/assets/6120ad02-1e66-4ef2-a11e-e6261262e5e7" />

Once you've "Minted" the "Genesis #0" iteration, you may create more on top of that stack:

<img width="416" height="80" alt="Screenshot from 2026-01-06 19-24-36" src="https://github.com/user-attachments/assets/4db09963-36c3-417f-b843-df30883ec693" />

By default, a new card will receive a Tarot Card with its associated upright meaning.

> [!IMPORTANT]
> **You may not change the details of your iteration once you "Mint" that iteration.**

<img width="482" height="877" alt="image" src="https://github.com/user-attachments/assets/d2841409-c958-4e9d-839a-5636a0bab4da" />

> [!WARNING]
> The server is protected with rate limiters and other mechanisms that prevents unauthorized access.


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
export DISCORD_TOKEN="<PUT_DISCORD_BOT_TOKEN_HERE>"
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
