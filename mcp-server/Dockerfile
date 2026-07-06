# claude-watch MCP server — deployable image with ffmpeg baked in.
# Serves the streamable-http transport so it can be added as a claude.ai
# custom connector (Remote MCP server URL: https://<your-host>/mcp).
FROM python:3.12-slim

# ffmpeg is the one non-pip dependency the pipeline needs.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY mcp-server/requirements.txt /app/mcp-server/requirements.txt
RUN pip install --no-cache-dir -r /app/mcp-server/requirements.txt

# Bring in the server + the skill it wraps (watch.py lives under .claude/).
COPY mcp-server /app/mcp-server
COPY .claude /app/.claude

ENV MCP_TRANSPORT=http \
    HOST=0.0.0.0 \
    PORT=8000
EXPOSE 8000

CMD ["python", "mcp-server/server.py"]
