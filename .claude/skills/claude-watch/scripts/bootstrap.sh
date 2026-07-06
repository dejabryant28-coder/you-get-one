#!/bin/bash
# Install the tools claude-watch needs, in ANY environment. Best-effort and
# idempotent, so the skill works in a fresh project with no setup hook.
set -uo pipefail

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "[claude-watch] installing ffmpeg ..."
  if command -v brew >/dev/null 2>&1; then
    brew install ffmpeg || true
  elif command -v sudo >/dev/null 2>&1 && command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg || true
  elif command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq && apt-get install -y -qq ffmpeg || true
  fi
fi

PIP="$(command -v pip3 || command -v pip || true)"
if [ -n "$PIP" ]; then
  echo "[claude-watch] ensuring yt-dlp, faster-whisper, requests ..."
  "$PIP" install --quiet --disable-pip-version-check yt-dlp faster-whisper requests || true
fi

if command -v ffmpeg >/dev/null 2>&1; then
  echo "[claude-watch] ready."
else
  echo "[claude-watch] ffmpeg still missing — install it manually (e.g. 'brew install ffmpeg' or 'apt-get install ffmpeg')."
fi
