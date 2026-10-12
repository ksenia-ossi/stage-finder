import re
import unicodedata

from .models import Job

IDF_HINTS = ["paris", "ile-de-france", "île-de-france", "idf", "hauts-de-seine", "seine-saint-denis",
             "val-de-marne", "val-d'oise", "yvelines", "essonne", "seine-et-marne", "la defense", "la défense",
             "boulogne", "neuilly", "issy", "levallois", "nanterre", "courbevoie", "puteaux", "montreuil",
             "saint-denis", "ivry", "massy", "versailles", "saclay", "cergy", "evry", "creteil", "vincennes",
             "clichy", "pantin", "rueil", "velizy", "guyancourt", "roissy", "orly", "le bourget"]
IDF_DEPT_RE = re.compile(r"(?<!\d)(75|77|78|91|92|93|94|95)(\d{3})?(?!\d)")
INTERNSHIP_SIGNALS = ["stage", "stagiaire", "internship", "intern ", "intern,", "intern-", "intern)", "alternance"]


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return " " + re.sub(r"\s+", " ", text.lower()) + " "


def _count(term: str, text: str) -> int:
    return text.count(_norm(term).strip())


def is_in_idf(job: Job) -> bool:
    loc = _norm(job.location)
    if loc.strip() in ("", "france"):
        return True
    return any(_norm(h).strip() in loc for h in IDF_HINTS) or bool(IDF_DEPT_RE.search(loc))


def is_internship(job: Job) -> bool:
    text = _norm(job.title + " " + job.contract)
    if any(s in text for s in ["intern", "stage", "stagiaire"]):
        return True
    return job.duration_min is not None


def excluded_by_title(job: Job, cfg: dict) -> str | None:
    title = _norm(job.title)
    for term in cfg.get("exclude_title_terms", []):
        if _norm(term).strip() in title:
            if term in ("cdi", "cdd") and ("stage" in title or "intern" in title):
                continue
            return term
    return None


def score(job: Job, cfg: dict) -> tuple[float, list[str]]:
    title = _norm(job.title)
    body = _norm(" ".join([job.summary, job.description]))
    tw = cfg.get("title_weight", 2.0)
    total = 0.0
    reasons = []

    for group, sign in (("skills", 1), ("boosts", 1), ("penalties", 1)):
        for term, weight in cfg.get(group, {}).items():
            t = _norm(term).strip()
            in_title = t in title
            in_body = t in body
            if not (in_title or in_body):
                continue
            pts = weight * (tw if in_title else 1.0)
            if group == "skills" and in_body:
                pts += min(_count(term, body) - 1, 3) * 0.5 * (1 if weight > 0 else -1)
            total += pts
            reasons.append(f"{'+' if pts >= 0 else ''}{pts:.0f} {term}{' (titre)' if in_title else ''}")

    if job.duration_min is not None or job.duration_max is not None:
        lo = job.duration_min or job.duration_max
        hi = job.duration_max or job.duration_min
        if lo <= 6 <= hi:
            total += 12
            reasons.append(f"+12 durée {lo}-{hi} mois")
        elif hi < 4:
            total -= 10
            reasons.append(f"-10 durée courte {hi} mois")
        elif lo > 6:
            total -= 5
            reasons.append(f"-5 durée {lo}+ mois")

    if not job.details_fetched:
        reasons.append("(description pas encore chargée)")

    reasons.sort(key=lambda r: -abs(float(r.split()[0])) if r[0] in "+-" else 0)
    return round(total, 1), reasons
