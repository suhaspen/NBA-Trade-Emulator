#!/usr/bin/env python3
"""
Merge Basketball-Reference contract dollars into your stats CSV (e.g. data/players.csv).

Uses TLS browser impersonation via curl_cffi when available (pip install curl-cffi).
Respect https://www.sports-reference.com/terms.html

Usage:
  pip install curl-cffi pandas lxml html5lib
  python merge_bref_salaries.py
  python merge_bref_salaries.py --players data/players.csv --season 2025-26
"""

from __future__ import annotations

import argparse
import os

from salary_data import merge_file


def main() -> None:
    ap = argparse.ArgumentParser(description="Merge BRef player contracts into players CSV")
    ap.add_argument("--players", default="data/players.csv", help="Stats CSV from fetch_nba_league_stats.py")
    ap.add_argument("--out", default=None, help="Output path (default: overwrite --players)")
    ap.add_argument(
        "--season",
        default=os.environ.get("NBA_STATS_SEASON"),
        help="Season id for salary column, e.g. 2025-26 (default: env NBA_STATS_SEASON or calendar current)",
    )
    args = ap.parse_args()
    merge_file(args.players, args.out, args.season)


if __name__ == "__main__":
    main()
