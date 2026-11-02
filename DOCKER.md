# Run Sillage on your server

Requires Git, Docker Engine with the Compose v2 plugin, and access to the private
repository. For GitHub SSH cloning, add the server's SSH key to your GitHub account
or add a read-only deploy key to this repository.

## First launch

Sillage is a single-owner app. The first account created becomes the owner;
registration then closes permanently while that account exists. Later visits
show sign-in only. Claim your account before sharing the public URL. If importing
an older database with several accounts, only the earliest-created account (lowest
ID) can sign in; other accounts and their data are preserved without access.

Run this one command on the server:

```sh
git clone git@github.com:epo-mae/Sillage.git && cd Sillage && docker compose up -d --build --wait
```

Open `http://127.0.0.1:18473`. The address is accessible only on the server itself. For remote browser access, follow
[CLOUDFLARE.md](CLOUDFLARE.md) to publish `https://sillage.example.com`.
The container starts on reboot as long as Docker
is enabled on startup. No Python installation is required on the host.

### Connect your Fragella account

On the server, in the Sillage folder:

```sh
cp docker.env.example .env
chmod 600 .env
nano .env
docker compose up -d
```

Set `FRAGELLA_API_KEY` to your existing key. Never commit this file. The key is not
baked into the image. Without it, the app uses the limited evaluation catalog.
For full catalog access on the first launch, create `.env` before running Compose.
To avoid storing the key in a file, export it in the shell before launching Compose.

### Internet access

For public access, put an HTTPS reverse proxy in front of port 8000 and set
`SILLAGE_SECURE_COOKIE=1`. Set `SILLAGE_BIND_ADDRESS=127.0.0.1` if that proxy is on
the host. Accessing the app over plain HTTP with secure cookies enabled prevents
login cookies from working. For a proxy in another container, connect both to a
shared Docker network rather than using its localhost to reach Sillage.

## Updates

From the Sillage folder, one command pulls changes and rebuilds/restarts the app:

```sh
git pull --ff-only && docker compose up -d --build --wait
```

Single-container updates briefly interrupt service. Keep a backup before updates.
The GitHub workflow builds and smoke-tests each push; it does not deploy to your server.

## Storage and backups

Accounts, fragrances, history, cached profiles, and the generated session signing
key are stored in the named volume `sillage-data`, mounted at `/app/data`. They
survive container rebuilds and normal `docker compose down` operations.
Do not run `docker compose down -v`: it deletes the volume and your data.
Run only one instance against this SQLite volume.

Consistent backup (briefly stops the app):

```sh
docker compose stop
docker run --rm -v sillage-data:/data:ro -v "$PWD:/backup" alpine tar czf /backup/sillage-backup.tgz -C /data .
docker compose start
```

Keep that archive private; it contains account data and signing material.

Restore to an existing initialized volume, replacing its contents:

```sh
docker compose stop
docker run --rm -v sillage-data:/data -v "$PWD:/backup:ro" alpine sh -c 'cd /data && rm -f sillage.db sillage.db-wal sillage.db-shm session.key && tar xzf /backup/sillage-backup.tgz && chown -R 10001:10001 /data'
docker compose start
```

## Move your existing Windows collection

A fresh server starts with no accounts or collection. Your local database is not
uploaded to GitHub. Stop the local app before copying `data/sillage.db` and
`data/session.key`; include any SQLite `-wal` and `-shm` files present after stopping.
Transfer these privately to the server, archive them without an enclosing `data`
directory, and restore them using the process above. If the source uses an explicit
`SILLAGE_SECRET_KEY`, configure that same key on the server instead of relying on
`session.key`. Do not copy a running SQLite database with an ordinary file copy.

## Operations

```sh
docker compose ps
docker compose logs --tail=100 -f
docker compose down
docker compose up -d --build --wait
```

The app runs as user 10001 with a read-only application filesystem and a health
check. A restart policy recovers exited processes; an unhealthy status alone does
not automatically restart a container. Docker can run this image on Linux amd64
or arm64 servers, building natively on the server.
