"""LinkedIn public (guest) job search - no login required."""
import logging
import re
import time
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from ..models import Job
from . import get

log = logging.getLogger(__name__)
NAME = "linkedin"
SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{id}"


def search(query: str, location: str, pages: int = 2) -> list[Job]:
    jobs = []
    start = 0
    for _ in range(pages):
        params = {"keywords": query, "location": location, "start": start}
        if "intern" in query.lower():
            params["f_JT"] = "I"
        r = get(f"{SEARCH_URL}?{urlencode(params)}")
        if r is None or not r.text.strip():
            break
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("div.base-search-card")
        found = 0
        for card in cards:
            link = card.select_one("a.base-card__full-link, a[href*='/jobs/view/']")
            title = card.select_one(".base-search-card__title")
            if not link or not title:
                continue
            href = link.get("href", "")
            m = re.search(r"-(\d{6,})(?:\?|$)", href.split("?")[0] + "?")
            if not m:
                continue
            job_id = m.group(1)
            company = card.select_one(".base-search-card__subtitle")
            loc = card.select_one(".job-search-card__location")
            date = card.select_one("time")
            jobs.append(Job(
                source=NAME,
                source_id=job_id,
                title=title.get_text(" ", strip=True),
                company=company.get_text(" ", strip=True) if company else "",
                url=f"https://www.linkedin.com/jobs/view/{job_id}/",
                location=loc.get_text(" ", strip=True) if loc else "",
                posted_at=(date.get("datetime") if date else "") or "",
                contract="Internship",
            ))
            found += 1
        if found < 10:
            break
        start += found
        time.sleep(0.8)
    return jobs


def fetch_details(job: Job) -> bool:
    r = get(DETAIL_URL.format(id=job.source_id))
    if r is None:
        return False
    soup = BeautifulSoup(r.text, "html.parser")
    desc = soup.select_one(".description__text")
    if desc:
        job.description = desc.get_text("\n", strip=True)
    for item in soup.select(".description__job-criteria-item"):
        parts = item.get_text("|", strip=True).split("|")
        if len(parts) >= 2 and "employment" in parts[0].lower():
            job.contract = parts[1]
    job.details_fetched = True
    return True
