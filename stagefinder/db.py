import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import Job

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "jobs.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    key TEXT PRIMARY KEY,
    source TEXT, source_id TEXT, dedupe_key TEXT,
    title TEXT, company TEXT, url TEXT, location TEXT, posted_at TEXT,
    contract TEXT, duration_min INTEGER, duration_max INTEGER,
    summary TEXT, description TEXT, details_fetched INTEGER DEFAULT 0,
    extra TEXT DEFAULT '{}',
    score REAL DEFAULT 0, reasons TEXT DEFAULT '[]',
    status TEXT DEFAULT 'new', notes TEXT DEFAULT '',
    first_seen TEXT, last_seen TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_dedupe ON jobs(dedupe_key);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started TEXT, finished TEXT, found INTEGER, new INTEGER, log TEXT
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def get_job(conn, key: str):
    return conn.execute("SELECT * FROM jobs WHERE key=?", (key,)).fetchone()


def job_from_row(row) -> Job:
    return Job(
        source=row["source"], source_id=row["source_id"], title=row["title"], company=row["company"],
        url=row["url"], location=row["location"] or "", posted_at=row["posted_at"] or "",
        contract=row["contract"] or "", duration_min=row["duration_min"], duration_max=row["duration_max"],
        summary=row["summary"] or "", description=row["description"] or "",
        details_fetched=bool(row["details_fetched"]), extra=json.loads(row["extra"] or "{}"),
    )


def upsert(conn, job: Job, score: float, reasons: list[str]) -> bool:
    """Insert or update a job. Returns True if the job is new."""
    existing = get_job(conn, job.key)
    ts = now()
    if existing is None:
        conn.execute(
            """INSERT INTO jobs (key, source, source_id, dedupe_key, title, company, url, location, posted_at,
               contract, duration_min, duration_max, summary, description, details_fetched, extra, score, reasons,
               first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (job.key, job.source, job.source_id, job.dedupe_key, job.title, job.company, job.url, job.location,
             job.posted_at, job.contract, job.duration_min, job.duration_max, job.summary, job.description,
             int(job.details_fetched), json.dumps(job.extra, ensure_ascii=False), score,
             json.dumps(reasons, ensure_ascii=False), ts, ts),
        )
        return True
    conn.execute(
        """UPDATE jobs SET title=?, company=?, location=?, posted_at=COALESCE(NULLIF(?,''), posted_at), contract=?,
           duration_min=?, duration_max=?, summary=?, description=?, details_fetched=?, extra=?, score=?, reasons=?,
           last_seen=? WHERE key=?""",
        (job.title, job.company, job.location, job.posted_at, job.contract, job.duration_min, job.duration_max,
         job.summary, job.description, int(job.details_fetched), json.dumps(job.extra, ensure_ascii=False),
         score, json.dumps(reasons, ensure_ascii=False), ts, job.key),
    )
    return False


def list_jobs(conn, status=None, source=None, min_score=None, q=None, hide_dupes=True, limit=500):
    where, args = [], []
    if status and status != "all":
        if status == "active":
            where.append("status NOT IN ('hidden','rejected')")
        else:
            where.append("status=?"); args.append(status)
    if source:
        where.append("source=?"); args.append(source)
    if min_score is not None:
        where.append("score>=?"); args.append(min_score)
    if q:
        where.append("(title LIKE ? OR company LIKE ? OR description LIKE ? OR location LIKE ?)")
        args += [f"%{q}%"] * 4
    sql = "SELECT * FROM jobs"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY score DESC, first_seen DESC LIMIT ?"
    args.append(limit)
    rows = [dict(r) for r in conn.execute(sql, args).fetchall()]
    for r in rows:
        r["reasons"] = json.loads(r["reasons"] or "[]")
        r["extra"] = json.loads(r["extra"] or "{}")
    if hide_dupes:
        seen, out = {}, []
        for r in rows:
            k = r["dedupe_key"]
            if k in seen:
                seen[k].setdefault("also_on", []).append({"source": r["source"], "url": r["url"]})
                continue
            seen[k] = r
            out.append(r)
        rows = out
    return rows


def set_status(conn, key: str, status: str | None = None, notes: str | None = None):
    if status is not None:
        conn.execute("UPDATE jobs SET status=? WHERE key=?", (status, key))
    if notes is not None:
        conn.execute("UPDATE jobs SET notes=? WHERE key=?", (notes, key))
    conn.commit()


def stats(conn) -> dict:
    row = conn.execute("""SELECT COUNT(*) total,
        SUM(status='new') new, SUM(status='applied') applied, SUM(status='saved') saved,
        SUM(status='hidden') hidden FROM jobs""").fetchone()
    last = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
    return {"counts": dict(row), "last_run": dict(last) if last else None}
