#!/usr/bin/env python3
"""CLI utility to explicitly seed or reset the GraphSupport AI Hackathon Demo scenario.

Usage:
    # Seed the demo customer, product, ticket, failed attempt, and conversations:
    python scripts/seed_demo.py

    # Check status of demo records:
    python scripts/seed_demo.py --status

    # Safely clear demo records only (nodes with id starting with 'demo-'):
    python scripts/seed_demo.py --reset
"""

import argparse
import sys

from graphsupport.application.demo_seed import (
    clear_hackathon_demo,
    is_hackathon_demo_seeded,
    seed_hackathon_demo,
)
from graphsupport.application.support_service import SupportService
from graphsupport.config import get_settings
from graphsupport.graph.driver import Neo4jDriverManager


def main() -> None:
    parser = argparse.ArgumentParser(description="GraphSupport AI - Hackathon Demo Scenario Seeder")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Safely remove all records starting with 'demo-' without touching real customer data.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Check whether the hackathon demo scenario is currently seeded.",
    )
    args = parser.parse_args()

    settings = get_settings()
    if not settings.is_neo4j_configured:
        print("❌ Error: Neo4j is not configured. Check your .env file.")
        sys.exit(1)

    manager = Neo4jDriverManager(settings=settings)
    if not manager.verify_connectivity():
        print("❌ Error: Unable to establish live connection to Neo4j instance.")
        sys.exit(1)

    service = SupportService(driver_manager=manager, database=settings.neo4j_database)

    if args.status:
        seeded = is_hackathon_demo_seeded(service)
        print(f"Hackathon demo status: {'SEEDED (Active)' if seeded else 'NOT SEEDED'}")
        sys.exit(0)

    if args.reset:
        count = clear_hackathon_demo(service)
        print(f"✅ Reset complete: {count} demo nodes safely removed.")
        sys.exit(0)

    # Default action: seed demo
    if is_hackathon_demo_seeded(service):
        print("ℹ️ Demo customer 'Sarah Chen' (demo-cust-sarah) is already seeded.")
        print("To recreate, first run: python scripts/seed_demo.py --reset")
        sys.exit(0)

    summary = seed_hackathon_demo(service)
    print("========================================================================")
    print(" GraphSupport AI — Hackathon Demo Scenario Seeded Successfully!")
    print("========================================================================")
    print(f" Customer: {summary['customer']['name']} ({summary['customer']['id']})")
    print(f" Product : {summary['product']['name']} ({summary['product']['sku']})")
    t_title = summary["ticket"]["title"]
    t_id = summary["ticket"]["id"]
    t_status = summary["ticket"]["status"]
    print(f" Ticket  : {t_title} [{t_id}] (Status: {t_status})")
    step_act = summary["troubleshooting_step"]["action"]
    step_out = summary["troubleshooting_step"]["outcome"].upper()
    print(f" Step 1  : {step_act} -> OUTCOME: {step_out}")
    c0 = summary["conversations"][0]
    c1 = summary["conversations"][1]
    print(f" Convs   : {c0} (Historical) & {c1} (Ready for Follow-up)")
    print("========================================================================")
    print("You can now test Conversation 2 in the Streamlit Support Chat workbench:")
    print("  1. Select persona: Sarah Chen (demo-cust-sarah)")
    print(f"  2. Select active session: {summary['conversations'][1]}")
    print("  3. Ask: 'My account still isn't working.'")
    print("========================================================================")


if __name__ == "__main__":
    main()
