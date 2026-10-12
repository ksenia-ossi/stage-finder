import json
import logging
import time
from pathlib import Path

from . import db
from .models import Job
from .scoring import excluded_by_title, is_in_idf, is_internship, score
from .sources import francetravail, hellowork, linkedin, wttj

log = logging.getLogger(__name__)
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"
SOURCES = {"linkedin": linkedin, "wttj": wttj, "hellowork": hellowork, "francetravail": francetravail}


def load_config(path: Path = CONFIG_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def collect(cfg: dict, progress=lambda msg: None) -> list[Job]:
    loc = cfg["location"]
    found: dict[str, Job] = {}

    def add(jobs, label):
        n = 0
        for j in jobs:
            if j.key not in found:
                found[j.key] = j
                n += 1
        progress(f"{label}: +{n} (total {len(found)})")

    for q in cfg["queries"]:
        add(linkedin.search(q, loc["linkedin"], cfg.get("linkedin_pages_per_query", 2)), f"LinkedIn '{q}'")
        add(wttj.search(q, loc["wttj_latlng"], loc["wttj_radius_m"], cfg.get("wttj_hits_per_query", 100)), f"WTTJ '{q}'")
        add(hellowork.search(q, loc["hellowork"], cfg.get("hellowork_pages_per_query", 2)), f"HelloWork '{q}'")
        if francetravail.enabled():
            add(francetravail.search(q, loc.get("francetravail_region", "11")), f"France Travail '{q}'")
    return list(found.values())


def run(cfg: dict | None = None, conn=None, progress=lambda msg: None, fetch_details: bool = True) -> dict:
    cfg = cfg or load_config()
    conn = conn or db.connect()
    started = db.now()
    log_lines = []

    def prog(msg):
        log_lines.append(msg)
        log.info(msg)
        progress(msg)

    jobs = collect(cfg, prog)
    kept, skipped = [], 0
    for j in jobs:
        reason = excluded_by_title(j, cfg)
        if reason:
            skipped += 1
            continue
        if not is_in_idf(j):
            skipped += 1
            continue
        if cfg.get("require_internship_signal") and not is_internship(j):
            skipped += 1
            continue
        kept.append(j)
    prog(f"Filtré: {len(kept)} gardées, {skipped} écartées (alternance/CDI/hors IDF)")

    budget = cfg.get("max_detail_fetches_per_run", 150)
    kept.sort(key=lambda j: -score(j, cfg)[0])
    new_count = 0
    for j in kept:
        existing = db.get_job(conn, j.key)
        if existing is not None and existing["details_fetched"]:
            old = db.job_from_row(existing)
            j.description, j.summary, j.details_fetched = old.description, old.summary, True
            j.posted_at = j.posted_at or old.posted_at
            j.extra = {**old.extra, **j.extra}
        elif fetch_details and not j.details_fetched and budget > 0:
            SOURCES[j.source].fetch_details(j)
            budget -= 1
            time.sleep(0.6)
        s, reasons = score(j, cfg)
        if db.upsert(conn, j, s, reasons):
            new_count += 1
    conn.commit()
    conn.execute("INSERT INTO runs (started, finished, found, new, log) VALUES (?,?,?,?,?)",
                 (started, db.now(), len(kept), new_count, "\n".join(log_lines)))
    conn.commit()
    prog(f"Terminé: {len(kept)} offres, {new_count} nouvelles")
    return {"found": len(kept), "new": new_count, "skipped": skipped, "log": log_lines}


def fetch_missing_details(cfg: dict | None = None, conn=None, progress=lambda msg: None, limit: int = 1000) -> int:
    """Load descriptions for jobs that were saved without them (score is recomputed)."""
    cfg = cfg or load_config()
    conn = conn or db.connect()
    rows = conn.execute("SELECT * FROM jobs WHERE details_fetched=0 AND status NOT IN ('hidden') "
                        "ORDER BY score DESC LIMIT ?", (limit,)).fetchall()
    done = 0
    for i, row in enumerate(rows, 1):
        j = db.job_from_row(row)
        if SOURCES[j.source].fetch_details(j):
            s, reasons = score(j, cfg)
            db.upsert(conn, j, s, reasons)
            done += 1
        if i % 10 == 0 or i == len(rows):
            conn.commit()
            progress(f"Descriptions chargées: {i}/{len(rows)}")
        time.sleep(0.6)
    conn.commit()
    return done
