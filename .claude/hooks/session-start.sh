#!/bin/bash
# SessionStart hook: install the runtime tools the claude-watch skill needs.
#
# Remote (Claude Code on the web) containers start clean, so ffmpeg / yt-dlp /
# faster-whisper have to be reinstalled each fresh environment. The container is
# cached after this hook completes, so later sessions in the same environment
# are fast. Idempotent and non-interactive.
set -euo pipefail

# Only run in the remote/web environment; local machines manage their own tools.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# --- ffmpeg (frame + audio extraction, spectrograms) ---
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "[session-start] installing ffmpeg ..."
  if command -v sudo >/dev/null 2>&1; then
    sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg
  else
    apt-get update -qq && apt-get install -y -qq ffmpeg
  fi
fi

# --- yt-dlp (download) + faster-whisper (free local transcription) + requests
# (hosted Whisper path). pip install is idempotent -- it no-ops when satisfied. ---
PIP="$(command -v pip3 || command -v pip)"
echo "[session-start] ensuring yt-dlp, faster-whisper, requests ..."
"$PIP" install --quiet --disable-pip-version-check yt-dlp faster-whisper requests

echo "[session-start] claude-watch dependencies ready."
