# claude-watch MCP server

Exposes the `claude-watch` pipeline as an **MCP server** so it works as a
**connector / integration** — in Claude chat, Cowork, Claude Desktop, or any MCP
client — not only as a Claude Code skill.

## Tools

| Tool | What it does |
|------|--------------|
| `watch_video(source, …)` | Downloads/reads a video, extracts scene-aware frames + transcript + audio, returns a structured breakdown (frame timestamps, transcript text, loudness summary). |
| `read_frames(out_dir, …)` | Returns the extracted frames as **images** so the model can see what's on screen. |

## Requirements

The **host running this server** needs the same tools as the skill:

- `ffmpeg` on PATH (required)
- `yt-dlp` (for URLs), `faster-whisper` (free local transcription)

```bash
pip install -r requirements.txt
# ffmpeg: brew install ffmpeg  |  apt-get install ffmpeg
```

## Run it

**Local (stdio)** — for Claude Desktop / Claude Code:

```bash
python server.py
```

Register it with Claude Code:

```bash
claude mcp add claude-watch -- python /absolute/path/to/mcp-server/server.py
```

Or add to a project's `.mcp.json`:

```json
{
  "mcpServers": {
    "claude-watch": {
      "command": "python",
      "args": ["/absolute/path/to/mcp-server/server.py"]
    }
  }
}
```

**Remote (HTTP)** — what a **claude.ai custom connector** needs:

```bash
MCP_TRANSPORT=http python server.py     # serves streamable-http
```

Put it behind HTTPS (a host that has ffmpeg), then in claude.ai add it as a
custom connector by URL. Note: claude.ai custom connectors generally expect an
authenticated HTTPS endpoint, so you'll want auth in front of it for anything
public.

## Usage

Ask Claude (once the connector is enabled):

> watch https://youtu.be/… and give me the hook + visual breakdown

Claude calls `watch_video`, then `read_frames(out_dir)` to see the frames, then
writes the breakdown pairing each frame with the transcript line at its
timestamp.

## Honest limits

- This is the *integration* path. It genuinely runs only where the host has
  ffmpeg/yt-dlp — a serverless chat with no compute can't execute it.
- Long videos: pass `start`/`end` to focus a section and keep the frame budget
  meaningful.

---

Adapted from the MIT-licensed
[`devinilabs/claude-watch`](https://github.com/devinilabs/claude-watch) skill.
