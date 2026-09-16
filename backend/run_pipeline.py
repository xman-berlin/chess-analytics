#!/usr/bin/env python3
"""One-shot sync + analyze + plan for local verification."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure backend package root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.analyzer import analyze_pending
from app.db import db
from app.insights import get_insights
from app.plan import generate_training_plan
from app.sync import sync_games


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full-sync", action="store_true")
    parser.add_argument("--limit", type=int, default=None, help="Analyse-Limit")
    parser.add_argument("--depth", type=int, default=None)
    args = parser.parse_args()

    if args.depth is not None:
        from app.config import get_settings

        get_settings.cache_clear()
        import os

        os.environ["ANALYSIS_DEPTH"] = str(args.depth)
        get_settings.cache_clear()

    db.init()
    print("Sync…")
    sync_result = sync_games(force_full=args.full_sync)
    print(json.dumps(sync_result, indent=2))

    print("Analyze…")
    analyze_result = analyze_pending(limit=args.limit)
    print(json.dumps({k: v for k, v in analyze_result.items() if k != "errors"}, indent=2))
    if analyze_result.get("errors"):
        print("Errors:", analyze_result["errors"][:5])

    print("Plan…")
    plan = generate_training_plan()
    print(f"Items: {len(plan['items'])}")
    for item in plan["items"]:
        print(f"  #{item['priority']} {item['title']} ({item['severity']})")

    insights = get_insights()
    print(
        f"Insights: {insights['games_count']} games, ACPL {insights['avg_acpl']}, "
        f"blunders/game {insights.get('avg_blunders_per_game')}"
    )


if __name__ == "__main__":
    main()
