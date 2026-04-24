"""Standalone test for the incentive parser. Read-only — does NOT write to DB.

Pulls current_incentive_raw from every building that has one and prints the
parsed output side-by-side. Run from project root:

    python3 backend/scripts/test_incentive_parser.py
"""
import json
import sys
import time
from pathlib import Path

# Ensure project root is on the path when running from anywhere.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.ai.incentive_parser import parse_incentive
from backend.app.database import SessionLocal
from backend.app.models import Building


def main():
    db = SessionLocal()
    try:
        buildings = (
            db.query(Building)
            .filter(Building.current_incentive_raw.isnot(None))
            .order_by(Building.name)
            .all()
        )
    finally:
        db.close()

    if not buildings:
        print("No buildings with incentive_raw in DB. Run a scrape first.")
        return

    print(f"Found {len(buildings)} buildings with incentives. Parsing...\n")
    print("=" * 80)

    for b in buildings:
        print(f"\n### {b.name} ({b.scraper_key})")
        print("-" * 80)
        print("RAW INPUT:")
        print(b.current_incentive_raw)
        print()

        t0 = time.time()
        result = parse_incentive(b.current_incentive_raw)
        elapsed = time.time() - t0

        print(f"PARSED OUTPUT ({elapsed:.2f}s):")
        print(json.dumps(result, indent=2))
        print("=" * 80)


if __name__ == "__main__":
    main()
