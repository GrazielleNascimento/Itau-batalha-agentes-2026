#!/usr/bin/env python3
"""Dispara um evento contra o endpoint /events, para ver a mensagem proativa.

    python3 data/generator/simulate_event.py --base-url http://localhost:8501
    python3 data/generator/simulate_event.py --base-url https://... \
        --token "$(gcloud auth print-identity-token)" --event invoice_due_soon
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

EXEMPLOS: dict[str, dict] = {
    "salary_received": {"amount": 5200.0},
    "spending_spike": {"category": "lazer", "amount": 890.0},
    "invoice_due_soon": {"due_date": "2026-10-05", "amount": 1240.75},
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", default="http://localhost:8501")
    ap.add_argument("--event", default="salary_received", choices=sorted(EXEMPLOS))
    ap.add_argument("--customer-id", default="FICT-0001")
    ap.add_argument("--token", default=None)
    args = ap.parse_args()

    payload = {
        "event_type": args.event,
        "customer_id": args.customer_id,
        "details": EXEMPLOS[args.event],
    }
    req = urllib.request.Request(
        f"{args.base_url.rstrip('/')}/events",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    if args.token:
        req.add_header("Authorization", f"Bearer {args.token}")

    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            corpo = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print(f"erro HTTP {e.code}: {e.read().decode()[:300]}", file=sys.stderr)
        return 1

    print(f"evento:  {corpo['event_type']}")
    print(f"sessão:  {corpo['session_id']}")
    print(f"\nmensagem proativa:\n  {corpo['message']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
