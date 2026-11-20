# RustDesk API server

A small server for the three things the free RustDesk ID/relay server leaves out: **sign-in**, **one
shared address book**, and **machines that list themselves**. One file of standard-library
Python, SQLite, no dependencies. Built to see how hard it is, from the client's own source, instead
of adopting an unmaintained community project.

Not a replacement for RustDesk's paid console: no web UI, no groups or permissions, no
single sign-on. The owners' RustDesk apps are the interface.

## What it does

| the client calls | what happens |
|---|---|
| `POST /api/login`, `/api/currentUser`, `/api/logout` | sign in with a name and password; a bearer token per sign-in |
| `GET /api/login-options` | answers `[]`: no third-party sign-in |
| `POST /api/ab/personal`, `/api/ab/settings` | answers **404**, which tells the client to use its *legacy* address book |
| `GET`, `POST /api/ab` | the whole address book as one JSON document, **shared by every user** |
| `POST /api/heartbeat`, `/api/sysinfo` | a machine reports itself; if it is new it appears in the book, tagged `new` |
| `POST /api/audit/conn`, `/file`, `/alarm` | kept, read with `server.py audit` |

A machine already in the book only has its hostname, login name and platform refreshed; its alias,
tags and saved password are the owners'. A machine an owner deletes stays deleted.

If the client is built with the `preset-address-book-tag` / `-alias` options, a new machine files
itself under that tag (a customer's name) instead of `new`.

## Running it

```bash
RUSTDESK_API_DB=./dev.db RUSTDESK_API_PASSWORD='a long passphrase' python3 server.py user add alice --admin
RUSTDESK_API_DB=./dev.db python3 server.py serve          # port 21114
```

Or the container: `docker build -t rustdesk-api .`, a volume on `/data`, and
`docker exec -e RUSTDESK_API_PASSWORD=... <name> python /app/server.py user add alice --admin`.
Passwords are 12 characters or more, stored as scrypt hashes; five failures lock an account for
five minutes.

## Trying it with the client

The tests (`python3 scripts/test_rustdesk_api.py`) replay exactly what the client sends, read from
its source. They cannot show that a real client accepts the answers. That is this step:

1. Start the server as above and add a user.
2. In RustDesk, **Settings, Network, ID/Relay server**, set **API server** to `http://<host>:21114`.
3. Click the account icon (or **Settings, Account**) and sign in.
4. The address book tab should open without an error. Add a peer, sign in on a second machine
   with the same account, and it should be there.
5. On a machine whose client has the API server set, wait a minute: it should appear in the book,
   tagged `new`. `server.py devices` lists what the server has heard.

If step 3 or 4 fails, read the server's stderr: every request is logged with its status, and a
`404` on a path not in the table above means the client wants something this does not do.

## Known limits

- **Read from client 1.5.3, tried against whatever you have.** The protocol is the client's and
  can change in a release. The tests pin what was read; a client that behaves differently is the
  thing to check first.
- **`/api/heartbeat` and `/api/sysinfo` carry no credentials** (the client sends none), so anyone
  who can reach the server can add entries to the book. Harmless on a tailnet. On a public address
  it needs a gate: the planned one is to accept a device only if the ID server has registered it,
  which needs the key.
- **A stale push can drop a machine.** The client saves the *whole* book. If an owner's app saved
  from an old copy in the seconds after a machine first appeared, that machine is gone until it is
  re-registered (a new uuid, or delete its row from `devices`). Rare; not guarded.
- **One address book.** Everybody who signs in sees and edits all of it.
- **Backup is the SQLite file.** It is in `/data`; the VM's backups cover it.
