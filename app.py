#!/usr/bin/env python3
"""Flask-Backend für den DHBW Lecture Timer."""

import sys
import os
import time
import threading
from datetime import datetime, timezone, timedelta

if sys.platform == "win32":
    os.system("")
    sys.stdout.reconfigure(encoding="utf-8")

from flask import Flask, jsonify, render_template
import requests as http_requests
from icalendar import Calendar

# ── Konfiguration ────────────────────────────────────────────────────────────
ICS_URL = "https://dhbw.app/ical/STG-TINF25D-KI"
REFRESH_INTERVAL = 300
USER_AGENT = "DHBW-LectureTimer/2.0"

app = Flask(__name__)

# ── Shared State ─────────────────────────────────────────────────────────────
_calendar: Calendar | None = None
_last_fetch: float = 0.0
_lock = threading.Lock()
_fetch_error: str | None = None


def ensure_aware(dt: datetime) -> datetime:
    """Naive datetimes → UTC; aware datetimes → UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def refresh_calendar() -> bool:
    """ICS-Feed herunterladen und parsen."""
    global _calendar, _last_fetch, _fetch_error
    try:
        resp = http_requests.get(
            ICS_URL,
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        resp.raise_for_status()
        cal = Calendar.from_ical(resp.text)
        with _lock:
            _calendar = cal
            _last_fetch = time.time()
            _fetch_error = None
        return True
    except Exception as exc:
        with _lock:
            _fetch_error = str(exc)
        return False


def _parse_events() -> list[dict]:
    """Alle Events aus dem gecachten Kalender extrahieren."""
    with _lock:
        cal = _calendar
    if cal is None:
        return []

    events = []
    for comp in cal.walk():
        if comp.name != "VEVENT":
            continue
        dtstart = comp.get("DTSTART")
        dtend = comp.get("DTEND")
        if not dtstart or not dtend:
            continue
        if not isinstance(dtstart.dt, datetime) or not isinstance(dtend.dt, datetime):
            continue

        start = ensure_aware(dtstart.dt)
        end = ensure_aware(dtend.dt)
        summary = str(comp.get("SUMMARY", "Unbekannt"))
        location = str(comp.get("LOCATION", "") or "")
        if location == "None":
            location = ""

        events.append(
            {
                "summary": summary,
                "location": location,
                "start": start.isoformat(),
                "end": end.isoformat(),
            }
        )

    events.sort(key=lambda e: e["start"])
    return events


# ── Routes ───────────────────────────────────────────────────────────────────


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    now_ts = time.time()
    if _calendar is None or (now_ts - _last_fetch) >= REFRESH_INTERVAL:
        refresh_calendar()

    now = datetime.now(timezone.utc)
    all_events = _parse_events()

    current = None
    next_event = None
    today_events: list[dict] = []

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    for ev in all_events:
        ev_start = datetime.fromisoformat(ev["start"])
        ev_end = datetime.fromisoformat(ev["end"])

        if ev_start < today_end and ev_end > today_start:
            today_events.append(ev)
        if ev_start <= now < ev_end and current is None:
            current = ev
        if ev_start > now and next_event is None:
            next_event = ev

    with _lock:
        error = _fetch_error

    return jsonify(
        {
            "current": current,
            "next": next_event,
            "today": today_events,
            "server_time": now.isoformat(),
            "error": error,
        }
    )


# ── Einstiegspunkt ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🔄  Lade Kalender …")
    if refresh_calendar():
        print("✅  Kalender geladen!")
    else:
        print("⚠   Kalender nicht erreichbar – Retry beim nächsten Request.")
    app.run(debug=True, host="127.0.0.1", port=5000)
