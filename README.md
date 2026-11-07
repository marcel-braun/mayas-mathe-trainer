# Mathe-Trainer

Spielerische Übungs-App für die Grundschule. Sie läuft lokal in Docker: die Flask-App und PostgreSQL. Es gibt keine Konten bei anderen Anbietern und keine externen Netzdienste im Browser.

## Start

Im Ordner der App:

```bash
docker compose up
```

Dann im Browser öffnen: <http://127.0.0.1:5050>

Der Host-Port ist `5050` und hört nur auf `127.0.0.1`. Beenden mit Strg+C. Mit `docker compose up -d` läuft es im Hintergrund, mit `docker compose down` stoppt es. Die Datenbank bleibt im Volume `mathe_pg` erhalten.

Beim ersten Start legt die App das Schema an und trägt zwei Nutzer ein, falls die Datenbank noch leer ist.

Verbindung zur Datenbank nur über die Variablen `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD` und `PGDATABASE`. In Compose stehen lokale Vorgaben (`mathe` / `mathe` / Datenbank `mathe`). Sie liegen nicht im Image. Eigene Werte setzt du vor dem Start, zum Beispiel `PGPASSWORD=geheim docker compose up`.

## Anmeldung

| Wer | Benutzername | Passwort | Rolle |
| --- | --- | --- | --- |
| Verwaltung | `admin` | `admin` | admin |
| Maya | `maya` | `maya` | kind, Anzeigename Maya |

Passwörter liegen gehasht in PostgreSQL (`hashlib.scrypt`). Die Sitzung liegt serverseitig, im Cookie steht nur eine Zufallskennung.

Die Verwaltung legt Kinder an, benennt sie um, setzt Passwörter und löscht sie. Der Admin-Zugang selbst lässt sich nicht löschen. Für ein Kind übt die Verwaltung auf der Übersichtsseite; die Versuche zählen für dieses Kind.

## Klassen, Modi, Runden

Die Klassenwahl 1 bis 4 setzt den Zahlenraum der deutschen Grundschule. Ein Modus zeigt nur Aufgaben, die diese Klasse schon kann. Uhr und Geld gibt es ab Klasse 2.

| Klasse | Zahlenraum und Stoff |
| --- | --- |
| 1 | bis 20: Plus, Minus, Zahlen vergleichen und ordnen, Formen, Längen vergleichen |
| 2 | bis 100: kleines Einmaleins, Uhr (volle und halbe Stunden), Cent bis 100, Längen in cm |
| 3 | bis 1000: Mal und Geteilt ohne Rest, Viertelstunden, Geld bis 20 Euro, m/cm, kg/g, Umfang |
| 4 | bis 1.000.000: schriftliches Addieren und Subtrahieren, Division mit Rest, Brüche, Uhr mit Minuten, Geld, km/m, Gewicht, Zeitspannen, Flächen |

Modi: Rechnen, Multiple Choice, Lückenaufgaben, Uhr, Geld, Größen, Formen und Geometrie, Zahlen ordnen.

Eine Runde hat 5, 10 oder 15 Aufgaben. Dieselbe Aufgabe kommt nicht direkt noch einmal. Am Ende steht eine kurze Auswertung, und bei einer gut gelaufenen Runde ein Feuerwerk.

Falsche Aufgaben werden gespeichert, je Kind, Klasse, Modus und Aufgabentyp. Schwache und frisch falsche Typen kommen im normalen Aufgabenstrom öfter wieder, sichere seltener. Auf der Kinderseite gibt es dafür keine Strafe. Die Verwaltung sieht die Übersicht unter Fortschritt.

Eine richtige Antwort startet ein Feuerwerk. Ab zwei richtigen Aufgaben hintereinander wird es stärker, ab fünf noch einmal.

## Schrift

Die Oberfläche nutzt die mitgelieferte Schrift Nunito (SIL Open Font License, Datei `static/fonts/Nunito.ttf`).
