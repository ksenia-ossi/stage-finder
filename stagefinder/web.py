import csv
import io
import logging
import threading

from flask import Flask, jsonify, render_template, request, Response

from . import db, search

log = logging.getLogger(__name__)
app = Flask(__name__)
conn = db.connect()
state = {"running": False, "log": [], "result": None}
lock = threading.Lock()


def _refresh():
    state["log"] = []
    try:
        res = search.run(conn=db.connect(), progress=lambda m: state["log"].append(m))
        state["result"] = res
    except Exception as e:  # noqa: BLE001
        log.exception("refresh failed")
        state["log"].append(f"Erreur: {e}")
    finally:
        state["running"] = False


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/jobs")
def jobs():
    min_score = request.args.get("min_score", type=float)
    rows = db.list_jobs(
        conn,
        status=request.args.get("status", "active"),
        source=request.args.get("source") or None,
        min_score=min_score,
        q=request.args.get("q") or None,
        hide_dupes=request.args.get("dupes") != "1",
    )
    return jsonify({"jobs": rows, "stats": db.stats(conn)})


@app.route("/api/jobs/<path:key>", methods=["PATCH"])
def update_job(key):
    data = request.get_json(force=True) or {}
    db.set_status(conn, key, status=data.get("status"), notes=data.get("notes"))
    return jsonify({"ok": True})


@app.route("/api/refresh", methods=["POST"])
def refresh():
    with lock:
        if state["running"]:
            return jsonify({"started": False, "running": True})
        state["running"] = True
        threading.Thread(target=_refresh, daemon=True).start()
    return jsonify({"started": True, "running": True})


@app.route("/api/status")
def status():
    return jsonify({"running": state["running"], "log": state["log"][-30:], "result": state["result"]})


@app.route("/api/config")
def config():
    return jsonify(search.load_config())


@app.route("/export.csv")
def export():
    rows = db.list_jobs(conn, status=request.args.get("status", "active"), limit=5000)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["score", "title", "company", "location", "contract", "duration", "posted_at", "source", "status", "url", "reasons"])
    for r in rows:
        dur = "-".join(str(x) for x in [r["duration_min"], r["duration_max"]] if x)
        w.writerow([r["score"], r["title"], r["company"], r["location"], r["contract"], dur,
                    (r["posted_at"] or "")[:10], r["source"], r["status"], r["url"], " | ".join(r["reasons"])])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=stages.csv"})


def main(host="127.0.0.1", port=5000):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    app.run(host=host, port=port, debug=False, threaded=True)
