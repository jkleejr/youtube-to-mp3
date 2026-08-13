#!/bin/zsh
# Launch Audio Grabber. Sets up the venv on first run, then starts the server
# and opens the app in your browser.
set -e
cd "$(dirname "$0")"

if [ ! -d venv ]; then
  echo "First run — setting up…"
  python3 -m venv venv
  venv/bin/pip install --quiet --upgrade pip yt-dlp flask
fi

# Keep yt-dlp fresh so YouTube/SoundCloud changes don't break downloads.
venv/bin/pip install --quiet --upgrade yt-dlp

( sleep 1 && open "http://127.0.0.1:5555" ) &
exec venv/bin/python app.py
