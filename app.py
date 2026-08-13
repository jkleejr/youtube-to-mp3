"""Local audio grabber: paste a YouTube or SoundCloud link, get an MP3 or WAV.

Runs a small Flask server on localhost. Downloads go straight to ~/Downloads.
"""

import os
import re
import subprocess
import threading
import uuid

from flask import Flask, jsonify, render_template, request
import yt_dlp

app = Flask(__name__)

DOWNLOAD_DIR = os.path.expanduser("~/Downloads")

# In-memory job store: job_id -> {status, progress, title, filename, error}
jobs = {}
jobs_lock = threading.Lock()

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def set_job(job_id, **fields):
    with jobs_lock:
        jobs[job_id].update(fields)


def make_hooks(job_id):
    def progress_hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes", 0)
            pct = (downloaded / total * 100) if total else 0
            set_job(job_id, status="downloading", progress=round(pct, 1))
        elif d["status"] == "finished":
            set_job(job_id, status="converting", progress=100)

    def postprocessor_hook(d):
        if d["status"] == "finished" and d.get("postprocessor") == "MoveFiles":
            info = d.get("info_dict", {})
            filepath = info.get("filepath") or info.get("_filename", "")
            set_job(
                job_id,
                status="done",
                progress=100,
                filename=os.path.basename(filepath),
                filepath=filepath,
            )

    return progress_hook, postprocessor_hook


def run_job(job_id, url, fmt):
    progress_hook, postprocessor_hook = make_hooks(job_id)

    postprocessor = {"key": "FFmpegExtractAudio", "preferredcodec": fmt}
    if fmt == "mp3":
        # 0 = best VBR quality ffmpeg's LAME encoder offers (~V0).
        postprocessor["preferredquality"] = "0"

    opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
        "noplaylist": True,
        "postprocessors": [postprocessor],
        "progress_hooks": [progress_hook],
        "postprocessor_hooks": [postprocessor_hook],
        "quiet": True,
        "noprogress": True,
        "windowsfilenames": False,
        "restrictfilenames": False,
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            set_job(job_id, title=info.get("title") or url)
            ydl.download([url])
        # Fallback in case the postprocessor hook didn't fire.
        with jobs_lock:
            if jobs[job_id]["status"] != "done":
                jobs[job_id].update(status="done", progress=100)
    except yt_dlp.utils.DownloadError as e:
        msg = ANSI_RE.sub("", str(e))
        set_job(job_id, status="error", error=msg)
    except Exception as e:  # noqa: BLE001 - surface anything to the UI
        set_job(job_id, status="error", error=str(e))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/convert", methods=["POST"])
def convert():
    data = request.get_json(force=True)
    url = (data.get("url") or "").strip()
    fmt = data.get("format", "mp3")

    if not url:
        return jsonify({"error": "Please paste a link first."}), 400
    if fmt not in ("mp3", "wav"):
        return jsonify({"error": "Format must be mp3 or wav."}), 400
    if not re.match(r"^https?://", url):
        return jsonify({"error": "That doesn't look like a valid link."}), 400

    job_id = uuid.uuid4().hex
    with jobs_lock:
        jobs[job_id] = {
            "status": "starting",
            "progress": 0,
            "title": None,
            "filename": None,
            "filepath": None,
            "error": None,
        }
    threading.Thread(target=run_job, args=(job_id, url, fmt), daemon=True).start()
    return jsonify({"job_id": job_id})


@app.route("/progress/<job_id>")
def progress(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            return jsonify({"error": "Unknown job."}), 404
        return jsonify({k: v for k, v in job.items() if k != "filepath"})


@app.route("/reveal/<job_id>", methods=["POST"])
def reveal(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
    if job and job.get("filepath") and os.path.exists(job["filepath"]):
        subprocess.Popen(["open", "-R", job["filepath"]])
        return jsonify({"ok": True})
    return jsonify({"error": "File not found."}), 404


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5555))
    print(f"\n  Audio Grabber running at  http://127.0.0.1:{port}\n")
    app.run(host="127.0.0.1", port=port, debug=False)
