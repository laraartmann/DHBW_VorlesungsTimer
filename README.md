#  DHBW.TIMER

Ein elegantes, modernes Web-Dashboard und CLI-Tool zur Live-Anzeige der verbleibenden Vorlesungszeit für DHBW-Studiengänge. Der Timer synchronisiert sich automatisch mit dem offiziellen iCal-Feed der **DHBW.app**.

---

##  Features

-  **Live Countdown**: Exakte Anzeige der verbleibenden Minuten und Sekunden der aktuellen Vorlesung.
-  **Fortschrittsanzeige**: Visueller Ring- und Balken-Fortschritt in Prozent.
-  **Vorlesungs-Details**: Automatische Anzeige von Modulname, Raumbezeichnung und Zeitraum.
-  **Tagesübersicht & Vorschau**: Übersicht aller heutigen Vorlesungen inklusive Vorschau auf den nächsten Termin.
-  **Auto-Sync**: Automatische Aktualisierung über den `.ics`-Kalenderfeed der DHBW.app.

---

##  Tech Stack

- **Backend:** Python (Flask / FastAPI)
- **Frontend:** HTML5, CSS3, JavaScript (Realtime Dashboard)
- **Parsing:** `icalendar` / `python-dateutil`

---
