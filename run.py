#!/usr/bin/env python3
"""Stage Finder - recherche rapide de stages Data en Île-de-France.

  python run.py web            # interface web sur http://127.0.0.1:5000
  python run.py search         # collecte + scoring, affiche le top en console
  python run.py search --no-details --top 40
  python run.py export out.csv
"""
import argparse
import logging
import sys

from stagefinder import db, search


def cmd_search(args):
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    conn = db.connect()
    res = search.run(conn=conn, fetch_details=not args.no_details)
    if not args.no_details:
        search.fetch_missing_details(conn=conn, progress=print)
    rows = db.list_jobs(conn, status="active", limit=args.top)
    print(f"\n{res['found']} offres, {res['new']} nouvelles. Top {len(rows)}:\n")
    for r in rows:
        flag = "NEW " if r["status"] == "new" else "    "
        dur = f" {r['duration_min']}-{r['duration_max']}m" if r["duration_min"] or r["duration_max"] else ""
        print(f"{flag}{r['score']:6.1f}  {r['title'][:60]:60}  {r['company'][:25]:25} {r['location'][:22]:22}{dur}  [{r['source']}]")
        print(f"         {r['url']}")


def cmd_export(args):
    conn = db.connect()
    rows = db.list_jobs(conn, status="active", limit=5000)
    import csv
    with open(args.path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["score", "title", "company", "location", "contract", "posted_at", "source", "status", "url"])
        for r in rows:
            w.writerow([r["score"], r["title"], r["company"], r["location"], r["contract"],
                        (r["posted_at"] or "")[:10], r["source"], r["status"], r["url"]])
    print(f"{len(rows)} lignes -> {args.path}")


def cmd_web(args):
    from stagefinder.web import main
    main(host=args.host, port=args.port)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search"); s.add_argument("--no-details", action="store_true"); s.add_argument("--top", type=int, default=30); s.set_defaults(fn=cmd_search)
    e = sub.add_parser("export"); e.add_argument("path"); e.set_defaults(fn=cmd_export)
    w = sub.add_parser("web"); w.add_argument("--host", default="127.0.0.1"); w.add_argument("--port", type=int, default=5000); w.set_defaults(fn=cmd_web)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
