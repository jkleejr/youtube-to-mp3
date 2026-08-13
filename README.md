# Audio Grabber

A local app that converts YouTube and SoundCloud links to MP3 or WAV in the best quality available. Audio only — video is never downloaded.

## Requirements

- macOS with `ffmpeg` installed (`brew install ffmpeg`)
- Python 3

## Run it

```
./run.sh
```

This opens the app at http://127.0.0.1:5555. Paste a link, pick MP3 or WAV, hit Convert. Files are saved to your **Downloads** folder.

- **MP3** — encoded at the highest VBR quality LAME offers (~V0, transparent for most listening)
- **WAV** — lossless conversion of the best audio stream available

The launcher auto-updates `yt-dlp` on every start so site changes don't break downloads.
