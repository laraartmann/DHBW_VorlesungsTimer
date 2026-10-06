#!/usr/bin/env python3
"""
DHBW Lecture Timer – Live-Countdown für die aktuelle Vorlesung.

Ruft den iCal-Feed für den Kurs STG-TINF25D-KI ab und zeigt einen
sekundengenau aktualisierten Countdown bis zum Vorlesungsende im Terminal an.
"""

import sys
import os
import time
from datetime import datetime, timezone, timedelta

# ── Windows-Konsole: UTF-8 erzwingen ────────────────────────────────────────
if sys.platform == "win32":
    os.system("")                              # aktiviert VT100 Escape-Codes
    sys.stdout.reconfigure(encoding="utf-8")   # UTF-8 statt cp1252

import requests
from icalendar import Calendar

# ── Konfiguration ────────────────────────────────────────────────────────────
ICS_URL = "https://dhbw.app/ical/STG-TINF25D-KI"
REFRESH_INTERVAL = 300          # Kalender alle 5 Minuten neu laden
RETRY_DELAY = 10                # Sekunden bis zum erneuten Versuch bei Fehler
USER_AGENT = "DHBW-LectureTimer/1.0"


# ── Hilfsfunktionen ─────────────────────────────────────────────────────────

def ensure_aware(dt: datetime) -> datetime:
    """Stelle sicher, dass ein datetime-Objekt timezone-aware (UTC) ist."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def fetch_calendar() -> Calendar | None:
    """Lade den ICS-Feed herunter und parse ihn.  Gibt None bei Fehler zurück."""
    try:
        resp = requests.get(
            ICS_URL,
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        resp.raise_for_status()
        return Calendar.from_ical(resp.text)
    except requests.RequestException as exc:
        print(f"\n⚠  Netzwerkfehler: {exc}")
        return None
    except Exception as exc:
        print(f"\n⚠  Parsing-Fehler: {exc}")
        return None


def find_current_event(cal: Calendar, now: datetime):
    """Finde das Event, das gerade stattfindet (now zwischen DTSTART und DTEND)."""
    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        dtstart = component.get("DTSTART")
        dtend = component.get("DTEND")
        if dtstart is None or dtend is None:
            continue

        start = ensure_aware(dtstart.dt) if isinstance(dtstart.dt, datetime) else None
        end = ensure_aware(dtend.dt) if isinstance(dtend.dt, datetime) else None

        if start is None or end is None:
            continue  # Ganztägige Events überspringen

        if start <= now < end:
            summary = str(component.get("SUMMARY", "– ohne Titel –"))
            location = str(component.get("LOCATION", "– kein Raum –"))
            return summary, location, start, end

    return None


def format_remaining(remaining: timedelta) -> str:
    """Formatiere die verbleibende Zeit als HH:MM:SS oder MM:SS."""
    total_seconds = int(remaining.total_seconds())
    if total_seconds < 0:
        return "00:00"

    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


# ── Hauptprogramm ───────────────────────────────────────────────────────────

def main() -> None:
    cal: Calendar | None = None
    last_fetch: float = 0.0

    print("╔══════════════════════════════════════════════╗")
    print("║     DHBW Vorlesungs-Timer  (STG-TINF25D-KI)  ║")
    print("╚══════════════════════════════════════════════╝")
    print()

    try:
        while True:
            now_ts = time.time()

            # ── Kalender (neu) laden ─────────────────────────────────────
            if cal is None or (now_ts - last_fetch) >= REFRESH_INTERVAL:
                print("\r🔄  Lade Kalender …                                    ", end="", flush=True)
                new_cal = fetch_calendar()
                if new_cal is not None:
                    cal = new_cal
                    last_fetch = now_ts
                else:
                    if cal is None:
                        print(f"\r⏳  Erneuter Versuch in {RETRY_DELAY} s …               ", end="", flush=True)
                        time.sleep(RETRY_DELAY)
                        continue

            # ── Aktuelles Event suchen ───────────────────────────────────
            now = datetime.now(timezone.utc)
            event = find_current_event(cal, now)

            if event is None:
                print(
                    "\r😴  Keine Vorlesung gerade – nächster Check in 30 s …       ",
                    end="",
                    flush=True,
                )
                time.sleep(30)
                continue

            summary, location, start, end = event
            remaining = end - now

            # ── Anzeige ──────────────────────────────────────────────────
            countdown = format_remaining(remaining)
            local_end = end.astimezone()  # lokale Zeitzone des Systems
            line = (
                f"\r📖  {summary}  |  📍 {location}  |  "
                f"⏱  {countdown} verbleibend  (Ende: {local_end:%H:%M})    "
            )
            print(line, end="", flush=True)

            # Vorlesung vorbei?
            if remaining.total_seconds() <= 0:
                print(f"\n\n✅  Vorlesung «{summary}» ist beendet!\n")
                cal = None  # Kalender neu laden für nächstes Event
                continue

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n👋  Timer beendet. Tschüss!")
        sys.exit(0)


if __name__ == "__main__":
    main()
