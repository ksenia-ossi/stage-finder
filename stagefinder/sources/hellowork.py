"""HelloWork (ex RegionsJob) - HTML search + JSON-LD job detail."""
import json
import logging
import re
import time
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from ..models import Job
from . import get

log = logging.getLogger(__name__)
NAME = "hellowork"
BASE = "https://www.hellowork.com"


def search(query: str, location: str, pages: int = 2) -> list[Job]:
    jobs = []
    for page in range(1, pages + 1):
        params = {"k": query, "l": location, "c": "Stage"}
        if page > 1:
            params["p"] = page
        r = get(f"{BASE}/fr-fr/emploi/recherche.html?{urlencode(params)}")
        if r is None:
            break
        soup = BeautifulSoup(r.text, "html.parser")
        found = 0
        for a in soup.select('a[data-cy="offerTitle"]'):
            href = a.get("href", "")
            m = re.search(r"/emplois/(\d+)\.html", href)
            if not m:
                continue
            card = a.find_parent(attrs={"data-cy": "serpCard"}) or a
            title_el = a.select_one("h3 p") or a
            company_el = a.select("h3 p")
            loc_el = card.select_one('[data-cy="localisationCard"]')
            contract_el = card.select_one('[data-cy="contractCard"]')
            jobs.append(Job(
                source=NAME,
                source_id=m.group(1),
                title=title_el.get_text(" ", strip=True),
                company=company_el[1].get_text(" ", strip=True) if len(company_el) > 1 else "",
                url=BASE + href,
                location=loc_el.get_text(" ", strip=True) if loc_el else "",
                contract=contract_el.get_text(" ", strip=True) if contract_el else "Stage",
            ))
            found += 1
        if found == 0:
            break
        time.sleep(0.8)
    return jobs


def fetch_details(job: Job) -> bool:
    r = get(job.url)
    if r is None:
        return False
    for m in re.finditer(r"<script[^>]*>(\s*\{.*?\})\s*</script>", r.text, re.S):
        raw = m.group(1)
        if '"JobPosting"' not in raw:
            continue
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("@type") == "JobPosting":
            desc = BeautifulSoup(d.get("description", ""), "html.parser").get_text("\n", strip=True)
            job.description = desc
            job.posted_at = d.get("datePosted", "") or job.posted_at
            et = d.get("employmentType")
            if et:
                job.contract = ", ".join(et) if isinstance(et, list) else str(et)
            sal = (d.get("baseSalary") or {}).get("value") or {}
            job.extra.update({"salary_min": sal.get("minValue"), "salary_max": sal.get("maxValue"),
                              "valid_through": d.get("validThrough")})
            break
    job.details_fetched = True
    return True
