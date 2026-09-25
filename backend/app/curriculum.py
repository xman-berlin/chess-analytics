from __future__ import annotations

from typing import Any

from .leaks import LABELS, LOST_EARLY, THROWN_DRAW, THROWN_WIN

# Standing study plan for the 1400–1800 band, weighted by the current game leak.
# Methods follow the same split as a club curriculum for that range: tactics are
# not the same skill as slow calculation, and the week still contains strategy,
# endgames, openings, and play. The emphasis moves with the games.


def _session(
    label: str,
    minutes: int,
    text: str,
    route: str | None = None,
    url: str | None = None,
    url_label: str | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {"label": label, "minutes": minutes, "text": text}
    if route:
        item["route"] = route
    if url:
        item["url"] = url
        item["url_label"] = url_label or url
    return item


def emphasis_ids(focus: str | None) -> list[str]:
    if focus == LOST_EARLY:
        return ["openings", "play"]
    if focus == THROWN_WIN:
        return ["tactics", "endgames", "play"]
    return ["tactics", "calculation", "play"]


def build_curriculum(
    focus: str | None,
    rating: int | None = None,
    practice_available: int = 0,
) -> dict[str, Any]:
    emphasis = emphasis_ids(focus)
    count = practice_available if practice_available > 0 else "die"
    focus_label = LABELS.get(focus) if focus else None
    rating_bit = f"{rating} Daily" if rating else "dein Daily-Niveau"

    areas = [
        {
            "id": "tactics",
            "title": "Taktik und Blunder-Check",
            "summary": (
                "Muster erkennen und den Zug prüfen, der dem Gegner eine Figur oder ein Matt schenkt, "
                "sind zwei verschiedene Übungen. Um 1500 bleiben einzügige Ausrutscher häufig, "
                "auch wenn die Partien insgesamt sauberer werden. Zuerst die eigenen Stellungen, "
                "danach erst ein kurzes Puzzle-Tempo."
            ),
            "sessions": [
                _session(
                    "Täglich",
                    15,
                    (
                        f"Öffne Üben. Dort liegen {count} Stellungen aus deinen Partien. "
                        "Das Brett steht so, wie es vor deinem Fehler stand. "
                        "Such den Zug, spiel ihn, und lies danach, welche Figur geschlagen wird oder hängen bleibt."
                    ),
                    route="/quiz",
                ),
                _session(
                    "Zusatz",
                    10,
                    "Ein kurzer Puzzle-Rush nur nach den eigenen Stellungen. Wer ein Motiv wiederholt verfehlt, übt genau dieses Motiv, nicht ein gemischtes Tempo.",
                    url="https://www.chess.com/puzzles/rush",
                    url_label="Puzzle Rush",
                ),
            ],
        },
        {
            "id": "calculation",
            "title": "Rechnung",
            "summary": (
                "Rechnung ist das langsame Durchspielen einer Variante, auch wenn kein Schlagzug da ist. "
                "Eine Stellung, die Lösung aufschreiben, dann erst die Begründung öffnen. "
                "Tempo ist hier kein Ziel."
            ),
            "sessions": [
                _session(
                    "Zwei Mal pro Woche",
                    20,
                    "Nimm eine Stellung in Üben. Schreib zuerst zwei mögliche Züge und die Folge auf, die du erwartest. Spiel den Zug erst danach und vergleiche deine Notiz mit der Begründung.",
                    route="/quiz",
                ),
            ],
        },
        {
            "id": "strategy",
            "title": "Strategie",
            "summary": (
                "Schwache Bauern, Vorposten und Bauernhebel werden in diesem Bereich langsam sichtbar. "
                "Die lange Strategie-Stunde lohnt, sobald die einzügigen Ausrutscher seltener sind. "
                "Bis dahin reicht eine Frage nach der Partie."
            ),
            "sessions": [
                _session(
                    "Nach der Partie",
                    10,
                    "Eine Frage beantworten: Welcher Bauer war schwach, welches Feld war ein Vorposten, welcher Bauernhebel war möglich?",
                    route="/games",
                ),
            ],
        },
        {
            "id": "endgames",
            "title": "Endspiele",
            "summary": (
                "Um 1500 gehen Vorteile oft verloren, weil der Turm passiv bleibt und ein Bauer festgehalten wird. "
                "Kurze technische Stellungen, plus die eigenen Partien, in denen ein klarer Vorteil abgegeben wurde."
            ),
            "sessions": [
                _session(
                    "Wöchentlich",
                    20,
                    "Eine Turmendspiel-Stellung: Aktivität vor dem Festhalten des Bauern. Kein neues Theoriekapitel.",
                    url="https://www.chess.com/endgames",
                    url_label="Endspiele",
                ),
            ],
        },
        {
            "id": "openings",
            "title": "Eröffnungen",
            "summary": (
                "In diesem Bereich trägt die Struktur mehr als neue Zugfolgen. "
                "Zu der Eröffnung, die du schon spielst, vier Fragen: Welchen Bauernhebel spiele ich? "
                "Welcher Tausch nützt mir? Auf welchen Feldern sollen die Figuren stehen? Was ist das Ziel der Struktur?"
            ),
            "sessions": [
                _session(
                    "Wöchentlich",
                    15,
                    "Eine schon gespielte Eröffnung, eine der vier Fragen, eine schriftliche Antwort. Keine neue Variante, solange die Partien nicht in der Eröffnung kippen.",
                    route="/games",
                ),
            ],
        },
        {
            "id": "play",
            "title": "Partien",
            "summary": (
                "Daily ist das Spieltraining. Am selben Tag nur die markierte Stelle ansehen "
                "und den Gedanken davor benennen, nicht die ganze Partie nacherzählen. "
                "Die Checkliste hat zwei Punkte, nicht zehn."
            ),
            "sessions": [
                _session(
                    "Am Partietag",
                    15,
                    "Partie öffnen, den markierten Zug ansehen, einen Satz schreiben: Was habe ich geprüft, was nicht?",
                    route="/games",
                ),
            ],
        },
    ]

    for area in areas:
        area["emphasis"] = area["id"] in emphasis

    plain_focus = {
        THROWN_DRAW: "Du standest ausgeglichen und hast die Partie mit einem Zug hergegeben.",
        THROWN_WIN: "Du standest klar besser und hast den Vorteil mit einem Zug abgegeben.",
        LOST_EARLY: "Die Partie war nach der Eröffnung nicht mehr ausgeglichen.",
    }.get(focus or "", "")

    week = [
        {
            "day": "Montag",
            "area": "tactics",
            "title": "Züge in Stellungen suchen, die du schon falsch gespielt hast",
            "minutes": 20,
            "detail": "Keine neue Partie. Drei Stellungen aus deinen eigenen Fehlern.",
            "steps": [
                "Öffne Üben. Das Brett zeigt die Stellung unmittelbar vor deinem Fehler. Du bist am Zug.",
                "Such den Zug selbst. Öffne die Partie nicht und lies die Lösung nicht vorher.",
                "Zieh die Figur auf das Feld.",
                "Lies den Text Warum. Dort steht, welche Figur der bessere Zug schlägt oder rettet, und was dein Zug dem Gegner erlaubt.",
                "Schreib einen Satz, zum Beispiel: „Ich habe den Läufer gezogen, der Springer konnte ihn danach schlagen.“",
                "Drei Stellungen reichen. Die nächste erscheint nach „Nächste Stellung“.",
            ],
        },
        {
            "day": "Dienstag",
            "area": "play",
            "title": "Eine beendete Daily-Partie an einer Stelle ansehen",
            "minutes": 15,
            "detail": "Nur der eine Zug, an dem die Stellung gekippt ist. Nicht die ganze Partie.",
            "steps": [
                "Nimm eine Daily-Partie, die heute oder gestern zu Ende gegangen ist.",
                "Öffne sie unter Partien. Oben steht die Auswertung, in der Zugliste ist eine Zeile markiert.",
                "Lies nur diese Zeile: welchen Zug du gespielt hast, und welcher besser war.",
                "Schreib einen Satz: Was hast du vor diesem Zug angeschaut, und was nicht?",
            ],
        },
        {
            "day": "Mittwoch",
            "area": "calculation",
            "title": "Eine Folge aufschreiben, bevor du den Zug siehst",
            "minutes": 25,
            "detail": "Eine einzige Stellung. Die Notiz kommt vor dem Ziehen.",
            "steps": [
                "Öffne Üben und nimm die erste Stellung.",
                "Schreib zwei Züge auf, die du für möglich hältst, und was der Gegner danach deiner Meinung nach tun kann.",
                "Erst jetzt zieh einen der beiden Züge auf dem Brett.",
                "Vergleiche deine Notiz mit dem Text Warum. Markiere, welcher Zug in deiner Notiz gefehlt hat.",
            ],
        },
        {
            "day": "Donnerstag",
            "area": "endgames",
            "title": "Ein Turmendspiel zu Ende spielen",
            "minutes": 20,
            "detail": "Eine Stellung auf chess.com. Kein Lehrbuchkapitel.",
            "steps": [
                "Öffne die Endspiel-Übungen auf chess.com und wähl eine Stellung mit Turm und Bauern.",
                "Spiel sie zu Ende.",
                "Wenn dein Turm nur einen Bauern bewacht, such stattdessen eine offene Linie oder ein Schach.",
                "Eine Stellung reicht.",
            ],
        },
        {
            "day": "Freitag",
            "area": "openings",
            "title": "Eine Frage zu einer Eröffnung, die du schon spielst",
            "minutes": 15,
            "detail": "Keine neuen Züge lernen.",
            "steps": [
                "Öffne Partien und nimm eine Eröffnung, die dort mehrfach vorkommt.",
                "Beantworte eine Frage schriftlich: Welchen Bauern will ich ziehen, um Linien zu öffnen? Oder: Welche Figur will ich tauschen?",
                "Die Antwort ist ein Satz, keine Zugfolge zum Auswendiglernen.",
            ],
        },
        {
            "day": "Samstag",
            "area": "strategy",
            "title": "Nachsehen, ob dieser Fehler seltener geworden ist",
            "minutes": 15,
            "detail": "Ein Blick in den Trainingsplan, dann eine Frage zu einer Partie.",
            "steps": [
                "Öffne den Trainingsplan. Dort steht, wie oft der aktuelle Fehler in den letzten 20 Partien vorkam, und ob das mehr oder weniger ist als zuvor.",
                "Nimm eine Partie aus dieser Woche.",
                "Beantworte eine Frage: Gab es einen schwachen Bauern, oder ein Feld, auf das eine Figur wollte?",
            ],
        },
        {
            "day": "Sonntag",
            "area": "rest",
            "title": "Nichts Neues lernen",
            "minutes": 0,
            "detail": "Kein Puzzle und keine Eröffnung.",
            "steps": [
                "Kein Puzzle, kein Video, keine neue Variante.",
                "Wenn du willst, lies den Satz vom Montag noch einmal, bevor du die nächste Daily-Partie anziehst.",
            ],
        },
    ]
    for row in week:
        row["emphasis"] = row["area"] in emphasis

    if focus_label:
        intro = (
            f"Lehrplan für {rating_bit}. Nächstes Etappenziel ist 1500. "
            f"Diese Woche geht es vor allem um „{focus_label}“: {plain_focus}"
        )
    else:
        intro = (
            f"Lehrplan für {rating_bit}. Die Gebiete stehen, das Gewicht folgt den Partien, "
            "sobald eine Auswertung da ist."
        )

    return {
        "intro": intro,
        "guidelines": [
            "Montag bis Mittwoch sind diese Woche die wichtigen Tage. Die übrigen Tage sind kurz.",
            "Montag suchst du den Zug auf dem Brett. Mittwoch schreibst du die Folge vorher auf. Das sind zwei verschiedene Aufgaben.",
            "Wenn du die Stellung in ein paar Sekunden triffst, nimm die nächste. Wenn du nach einer Viertelstunde nur rätst, brich ab und lies die Begründung.",
        ],
        "areas": areas,
        "week": week,
        "emphasis": emphasis,
        "focus_label": focus_label,
    }
