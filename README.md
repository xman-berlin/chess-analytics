# Chess Analytics

Lokale App für **TorstenGeise**: Daily-Partien von chess.com syncen, mit Stockfish analysieren, Schwächen aggregieren und einen persönlichen Trainingsplan aktualisieren.

## Voraussetzungen

- Python 3.11+
- Node.js 20+
- [Stockfish](https://stockfishchess.org/) im PATH oder Pfad in `backend/.env`

```bash
# macOS
brew install stockfish
```

## Start

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # ggf. STOCKFISH_PATH anpassen
uvicorn app.main:app --reload --port 8000
```

API: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
npm start
```

UI: http://localhost:4200

## So nutzt du den Plan

1. Im Dashboard **Jetzt syncen & analysieren** klicken (holt Daily-Partien, analysiert die neuesten ~50).
2. Unter **Trainingsplan** die priorisierten Fokusbereiche abarbeiten — Aufgaben kommen aus *deinen* Fehlern, nicht aus generischen Tipps.
3. Nach jeder abgeschlossenen Daily-Partie: innerhalb 24h in **Partien** öffnen und kritische Züge ansehen.
4. Alle 6 Stunden synct der Scheduler automatisch; Plan bei Bedarf mit **Plan aktualisieren** neu berechnen.

Typisch bei ~1400 Daily und höherem Taktik-Rating: weniger neue Eröffnungen pauken, mehr Blunder-Check in Partien, Endspiele und Review der eigenen kritischen Stellungen.

## Konfiguration (`backend/.env`)

| Variable | Bedeutung |
|----------|-----------|
| `CHESS_USERNAME` | chess.com Username |
| `TIME_CLASSES` | z.B. `daily` (später `daily,rapid`) |
| `STOCKFISH_PATH` | Pfad zur Engine |
| `ANALYSIS_DEPTH` | Stockfish-Tiefe (Default 16) |
| `ANALYSIS_LIMIT` | Max. Partien pro Analyse-Lauf |
| `SYNC_INTERVAL_HOURS` | Scheduler-Intervall |
