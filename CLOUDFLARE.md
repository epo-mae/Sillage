# Publish Sillage at sillage.example.com

Sillage publishes only on `127.0.0.1:18473` by default. This dedicated port avoids
the common port 8000; if another service uses it, change `SILLAGE_PUBLIC_PORT` and
the tunnel origin together. The app still listens on port 8000 inside its container.

## Start or update the app

In the repository folder on your Linux server:

```sh
git pull --ff-only
```

Set these values in `.env`, preserving any other settings and your Fragella key:

```dotenv
SILLAGE_BIND_ADDRESS=127.0.0.1
SILLAGE_PUBLIC_PORT=18473
SILLAGE_SECURE_COOKIE=1
```

Then run:

```sh
docker compose up -d --build --wait
curl --fail http://127.0.0.1:18473/ -o /dev/null
```

The public URL uses HTTPS. With secure cookies enabled, use the public HTTPS URL
for login rather than the local HTTP URL.

## If your existing tunnel is managed in the Cloudflare dashboard

Open your existing tunnel's published application routes/public hostnames and add:

| Setting | Value |
| --- | --- |
| Subdomain | `sillage` |
| Domain | `example.com` |
| Path | Leave empty |
| Service type | HTTP |
| Service URL | `127.0.0.1:18473` |

This assumes cloudflared runs directly on the same server as Sillage. Saving the
route creates the DNS record. No new tunnel or connector token is needed.
If the hostname already has a DNS record, check its existing purpose before
changing it. The domain must be managed in your Cloudflare account.

## If your existing tunnel uses a local configuration file

Keep its existing tunnel ID, credentials, and routes. In the configuration used by
the running service (commonly `/etc/cloudflared/config.yml`), add this rule inside
the existing `ingress:` list, before any wildcard matching this domain and before
the final catch-all rule:

```yaml
  - hostname: sillage.example.com
    service: http://127.0.0.1:18473
```

Do not replace the entire file or add a second `ingress:` key. Using the actual
configuration path if it differs, validate before restarting:

```sh
sudo cloudflared tunnel --config /etc/cloudflared/config.yml ingress validate
sudo cloudflared tunnel --config /etc/cloudflared/config.yml ingress rule https://sillage.example.com
```

Create the DNS route using a cloudflared CLI authenticated to your Cloudflare account:

```sh
cloudflared tunnel route dns YOUR_EXISTING_TUNNEL_NAME_OR_ID sillage.example.com
sudo systemctl restart cloudflared
curl -I https://sillage.example.com
```

Replace `YOUR_EXISTING_TUNNEL_NAME_OR_ID` with your existing tunnel name or UUID.
The service restart command assumes a Linux systemd service called `cloudflared`.
Use the dashboard route method instead for remotely managed/token-based tunnels;
local ingress edits do not configure those tunnels.

## If cloudflared itself runs in Docker

Inside a container, `127.0.0.1` refers to that container. Connect cloudflared and
Sillage to a shared Docker network instead. For example, if the existing connector
is attached to a network called `cloudflare`, create `compose.override.yaml`:

```yaml
services:
  sillage:
    networks:
      - cloudflare
networks:
  cloudflare:
    external: true
    name: cloudflare
```

Use the actual existing network name; the connector must also be attached to it.
Run `docker compose up -d`, then use **`http://sillage:8000`** as the tunnel service
instead of `http://127.0.0.1:18473`. Keep the host port loopback-only. Do not commit
server-specific overrides; they are ignored by Git.

## Reference

- [Cloudflare routing](https://developers.cloudflare.com/tunnel/concepts/routing/)
- [Local ingress configuration](https://developers.cloudflare.com/tunnel/features/locally-managed-tunnels/configuration-file/)
- [Create a DNS route](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/local-management/create-local-tunnel/)
