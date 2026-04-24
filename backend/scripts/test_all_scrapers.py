"""Run all 11 scrapers against a fresh DB and print a detailed report.

Usage (from project root):
    python3 backend/scripts/test_all_scrapers.py

What it does:
    1. Deletes backend/data/app.db if present.
    2. Re-runs init_db (creates tables, seeds 11 buildings + 2 users).
    3. Instantiates every registered scraper and runs them all in parallel.
    4. Queries the resulting DB state and prints per-building details:
         - scrape status, error (if any), source URL
         - unit count + breakdown by unit_type
         - sample units (first 3) with rent/sqft/floor/availability
         - raw incentive text (if any)
         - parsed incentive JSON (if the parser succeeded)

No arguments. No options. Just fresh data → report.
"""
import asyncio
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.database import SessionLocal, engine, Base
from backend.app.init_db import seed_buildings, seed_users
from backend.app.models import Building, Unit
from backend.app.scrapers.runner import run_scrapers

# Import every scraper. Montgomery is included — it returns a failed result
# cleanly (Cloudflare short-circuit), which is exactly the honest-failure
# case we want to exercise.
from backend.app.scrapers.parker import ParkerScraper
from backend.app.scrapers.story_of_midtown import (
    StoryOfMidtown73Scraper,
    StoryOfMidtown75Scraper,
)
from backend.app.scrapers.selby import SelbyScraper
from backend.app.scrapers.ecentral import ECentralScraper
from backend.app.scrapers.themontgomery import TheMontgomeryScraper
from backend.app.scrapers.thewhitney import WhitneyScraper
from backend.app.scrapers.thehampton import TheHamptonScraper
from backend.app.scrapers.e18hteen import E18hteenScraper
from backend.app.scrapers.corner_on_broadway import CornerOnBroadwayScraper
from backend.app.scrapers.akoya import AkoyaScraper


ALL_SCRAPERS = [
    ParkerScraper(),
    StoryOfMidtown73Scraper(),
    StoryOfMidtown75Scraper(),
    SelbyScraper(),
    ECentralScraper(),
    TheMontgomeryScraper(),
    WhitneyScraper(),
    TheHamptonScraper(),
    E18hteenScraper(),
    CornerOnBroadwayScraper(),
    AkoyaScraper(),
]


def reset_db():
    """Drop + recreate all tables, re-seed buildings and users."""
    db_path = ROOT / "backend" / "data" / "app.db"
    if db_path.exists():
        db_path.unlink()
        print(f"  deleted {db_path}")

    Base.metadata.create_all(bind=engine)
    print("  tables created")

    db = SessionLocal()
    try:
        nb = seed_buildings(db)
        nu = seed_users(db)
        print(f"  seeded {nb} buildings, {nu} users")
    finally:
        db.close()


def print_run_summary(run_summary: dict):
    """Top-line from run_scrapers: run id, status counts, total units."""
    print()
    print("=" * 80)
    print("RUN SUMMARY")
    print("=" * 80)
    print(f"  run_id:              {run_summary['run_id']}")
    print(f"  status:              {run_summary['status']}")
    print(f"  buildings_attempted: {run_summary['buildings_attempted']}")
    print(f"  buildings_succeeded: {run_summary['buildings_succeeded']}")
    print(f"  total_units_found:   {run_summary['total_units_found']}")


def print_building_details():
    """Query the DB for every building and print a full detail block."""
    db = SessionLocal()
    try:
        buildings = db.query(Building).order_by(Building.name).all()

        for b in buildings:
            units = (
                db.query(Unit)
                .filter(Unit.building_id == b.id, Unit.is_currently_available == True)
                .all()
            )

            print()
            print("=" * 80)
            print(f"{b.name}  ({b.scraper_key})")
            print("-" * 80)
            print(f"  status:         {b.last_scrape_status}")
            if b.last_scrape_error:
                print(f"  error:          {b.last_scrape_error}")
            print(f"  source_url:     {b.source_url or '(none)'}")
            print(f"  units:          {len(units)}")

            if units:
                by_type = Counter(u.unit_type for u in units)
                type_str = ", ".join(f"{t}={n}" for t, n in sorted(by_type.items()))
                print(f"  by unit_type:   {type_str}")

                rents = [u.rent for u in units if u.rent]
                if rents:
                    print(f"  rent range:     ${min(rents):,.0f} – ${max(rents):,.0f}")

                print(f"  sample units:")
                for u in units[:3]:
                    parts = [f"id={u.unit_identifier}"]
                    parts.append(f"type={u.unit_type}")
                    parts.append(f"rent=${u.rent:,.0f}")
                    if u.sqft:
                        parts.append(f"sqft={u.sqft}")
                    if u.floor is not None:
                        parts.append(f"floor={u.floor}")
                    if u.available_date:
                        parts.append(f"avail={u.available_date}")
                    print(f"    - {' | '.join(parts)}")

            # Incentive block
            if b.current_incentive_raw:
                print(f"  incentive_source: {b.incentive_source_url or '(none)'}")
                print(f"  incentive_raw:")
                for line in b.current_incentive_raw.splitlines():
                    print(f"    | {line}")
                if b.current_incentive_parsed:
                    print(f"  incentive_parsed:")
                    parsed_str = json.dumps(b.current_incentive_parsed, indent=2)
                    for line in parsed_str.splitlines():
                        print(f"    {line}")
            else:
                print(f"  incentive:      (none captured)")
    finally:
        db.close()


def print_final_tally():
    """One-line-per-building summary at the bottom for quick scanning."""
    db = SessionLocal()
    try:
        buildings = db.query(Building).order_by(Building.name).all()
        print()
        print("=" * 80)
        print("FINAL TALLY")
        print("=" * 80)
        print(f"{'building':<40} {'status':<10} {'units':>6}  {'incentive'}")
        print("-" * 80)
        total_units = 0
        total_incentives = 0
        for b in buildings:
            n = (
                db.query(Unit)
                .filter(Unit.building_id == b.id, Unit.is_currently_available == True)
                .count()
            )
            total_units += n
            has_inc = "YES" if b.current_incentive_raw else "-"
            if b.current_incentive_raw:
                total_incentives += 1
            print(f"{b.name:<40} {b.last_scrape_status:<10} {n:>6}  {has_inc}")
        print("-" * 80)
        print(f"{'TOTAL':<40} {'':<10} {total_units:>6}  {total_incentives} with incentives")
    finally:
        db.close()


async def main():
    print("=" * 80)
    print("FULL PIPELINE TEST — all 11 scrapers, fresh DB, parallel execution")
    print("=" * 80)

    print("\n[1/3] Resetting database...")
    reset_db()

    print(f"\n[2/3] Running {len(ALL_SCRAPERS)} scrapers in parallel...")
    print("      (Playwright scrapers take 15-60s each; gateway API scrapers <2s.)")
    t0 = time.time()
    run_summary = await run_scrapers(ALL_SCRAPERS)
    elapsed = time.time() - t0
    print(f"      finished in {elapsed:.1f}s")

    print("\n[3/3] Reading back from DB...")
    print_run_summary(run_summary)
    print_building_details()
    print_final_tally()


if __name__ == "__main__":
    asyncio.run(main())
