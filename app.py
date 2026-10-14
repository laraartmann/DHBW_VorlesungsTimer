#!/usr/bin/env python3
"""Flask-Backend für den DHBW Lecture Timer."""

import sys
import os
import re
import time
import threading
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

if sys.platform == "win32":
    os.system("")
    sys.stdout.reconfigure(encoding="utf-8")

from flask import Flask, jsonify, render_template, request
import requests as http_requests
from icalendar import Calendar

# ── Konfiguration ────────────────────────────────────────────────────────────
ICS_URL = "https://dhbw.app/ical/{course}"
COURSES_URL = "https://api.dhbw.app/courses"
DEFAULT_COURSE = "STG-TINF25D-KI"
# Nur Fallback, falls die Kursliste nicht erreichbar ist – Kursnamen enthalten
# u. a. Umlaute, "_", "+", "#" und "." und können sehr lang sein.
COURSE_RE = re.compile(r"^[^\s/\?]{2,100}$")
REFRESH_INTERVAL = 300
COURSES_REFRESH_INTERVAL = 24 * 3600
USER_AGENT = "DHBW-LectureTimer/2.0"

app = Flask(__name__)

# ── Shared State (pro Kurs) ──────────────────────────────────────────────────
_calendars: dict[str, Calendar] = {}
_last_fetch: dict[str, float] = {}
_fetch_errors: dict[str, str | None] = {}
_lock = threading.Lock()

_courses: list[str] = []
_courses_fetch: float = 0.0


def ensure_aware(dt: datetime) -> datetime:
    """Naive datetimes → UTC; aware datetimes → UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def refresh_calendar(course: str) -> bool:
    """ICS-Feed eines Kurses herunterladen und parsen."""
    try:
        resp = http_requests.get(
            ICS_URL.format(course=quote(course, safe="")),
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        resp.raise_for_status()
        cal = Calendar.from_ical(resp.text)
        with _lock:
            _calendars[course] = cal
            _last_fetch[course] = time.time()
            _fetch_errors[course] = None
        return True
    except Exception as exc:
        with _lock:
            _fetch_errors[course] = str(exc)
        return False


def refresh_courses() -> None:
    """Kursliste von der DHBW.app-API laden."""
    global _courses, _courses_fetch
    try:
        resp = http_requests.get(
            COURSES_URL,
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        resp.raise_for_status()
        courses = sorted({c for c in resp.json() if isinstance(c, str)})
        with _lock:
            _courses = courses
            _courses_fetch = time.time()
    except Exception:
        pass


def _parse_events(course: str) -> list[dict]:
    """Alle Events aus dem gecachten Kalender eines Kurses extrahieren."""
    with _lock:
        cal = _calendars.get(course)
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


@app.route("/kurse")
def courses_page():
    return render_template("courses.html")


def get_courses() -> list[str]:
    """Gecachte Kursliste, bei Bedarf neu geladen."""
    if not _courses or (time.time() - _courses_fetch) >= COURSES_REFRESH_INTERVAL:
        refresh_courses()
    with _lock:
        return list(_courses)


def is_valid_course(course: str) -> bool:
    courses = get_courses()
    if courses:
        return course in courses
    return bool(COURSE_RE.match(course))


@app.route("/api/courses")
def api_courses():
    return jsonify({"courses": get_courses(), "default": DEFAULT_COURSE})


@app.route("/api/status")
def api_status():
    course = request.args.get("course", DEFAULT_COURSE).strip()
    if not is_valid_course(course):
        return jsonify({"error": f"Ungültiger Kurs: {course}"}), 400

    now_ts = time.time()
    if course not in _calendars or (now_ts - _last_fetch.get(course, 0.0)) >= REFRESH_INTERVAL:
        refresh_calendar(course)

    now = datetime.now(timezone.utc)
    all_events = _parse_events(course)

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
        error = _fetch_errors.get(course)

    return jsonify(
        {
            "course": course,
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
    if refresh_calendar(DEFAULT_COURSE):
        print("✅  Kalender geladen!")
    else:
        print("⚠   Kalender nicht erreichbar – Retry beim nächsten Request.")
    app.run(debug=True, host="127.0.0.1", port=5000)
