# Deploy the claude-watch MCP server as a claude.ai connector

The "Add custom connector" dialog asks for a **Remote MCP server URL** — a public
HTTPS endpoint. So the server has to run somewhere reachable. This is the step
that turns `server.py` into a URL you can paste.

## What goes in the dialog

| Field | Value |
|-------|-------|
| **Name** | anything, e.g. `claude-watch` |
| **Remote MCP server URL** | `https://<your-host>/mcp` (the `/mcp` path is the streamable-http endpoint) |
| **OAuth Client ID / Secret** | optional — leave blank unless you put OAuth in front (see Security) |

You can't fill in the URL until the server is deployed. Do that first.

## Deploy (Docker, works on most hosts)

The `Dockerfile` bakes in ffmpeg and serves HTTP. From the repo root:

```bash
docker build -f mcp-server/Dockerfile -t claude-watch-mcp .
docker run -p 8000:8000 claude-watch-mcp
# local endpoint: http://localhost:8000/mcp
```

Push that image to a host that gives you a public HTTPS URL:

- **Railway / Render / Fly.io** — point them at this repo + `mcp-server/Dockerfile`;
  they inject `$PORT` (the server already binds `0.0.0.0:$PORT`) and give you an
  HTTPS domain. Your connector URL is `https://<domain>/mcp`.
- **Any VM** — `docker run` behind a reverse proxy (Caddy/nginx) with TLS.

Then paste `https://<domain>/mcp` into the dialog.

## Security (read before exposing it publicly)

This server shells out to `yt-dlp` and `ffmpeg` on URLs the caller provides. An
open public endpoint is an abuse/resource risk. Before sharing the URL:

- Keep the URL private (only in your own connector settings), and/or
- Put auth in front — a reverse proxy requiring a bearer token, or an OAuth proxy
  (then use the dialog's OAuth fields). The dialog's own warning — "only use
  connectors from developers you trust" — applies; here that developer is you.

## Don't need the URL? Use it locally instead

For Claude Desktop / Claude Code you don't need this dialog at all — run it over
stdio (no hosting):

```bash
claude mcp add claude-watch -- python /abs/path/mcp-server/server.py
```

See `README.md` for the stdio setup.
