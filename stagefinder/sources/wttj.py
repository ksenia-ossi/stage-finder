"""Welcome to the Jungle - public Algolia search index used by the website."""
import logging

import requests

from ..models import Job
from . import HEADERS

log = logging.getLogger(__name__)
NAME = "wttj"
APP_ID = "CSEKHVMS53"
API_KEY = "4bd8f6215d0cc52b26430765769e65a0"
URL = f"https://{APP_ID.lower()}-dsn.algolia.net/1/indexes/*/queries"
INDEX = "wttj_jobs_production_fr"


def search(query: str, latlng: str, radius_m: int, hits: int = 100) -> list[Job]:
    params = (
        f"query={requests.utils.quote(query)}&hitsPerPage={hits}"
        f"&filters=contract_type:internship&aroundLatLng={latlng}&aroundRadius={radius_m}"
    )
    body = {"requests": [{"indexName": INDEX, "params": params}]}
    headers = dict(HEADERS, **{
        "Referer": "https://www.welcometothejungle.com/",
        "Origin": "https://www.welcometothejungle.com",
        "content-type": "application/json",
    })
    try:
        r = requests.post(
            f"{URL}?x-algolia-application-id={APP_ID}&x-algolia-api-key={API_KEY}",
            json=body, headers=headers, timeout=25,
        )
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError) as e:
        log.warning("WTTJ search failed: %s", e)
        return []
    jobs = []
    for hit in data.get("results", [{}])[0].get("hits", []):
        org = hit.get("organization") or {}
        offices = hit.get("offices") or [{}]
        office = offices[0] if offices else {}
        loc = ", ".join(filter(None, [office.get("city"), office.get("state")]))
        description = "\n".join(filter(None, [
            hit.get("summary") or "",
            " ".join(hit.get("key_missions") or []) if isinstance(hit.get("key_missions"), list) else (hit.get("key_missions") or ""),
            hit.get("profile") or "",
        ]))
        jobs.append(Job(
            source=NAME,
            source_id=hit.get("reference") or hit.get("objectID"),
            title=hit.get("name", ""),
            company=org.get("name", ""),
            url=f"https://www.welcometothejungle.com/fr/companies/{org.get('slug')}/jobs/{hit.get('slug')}",
            location=loc,
            posted_at=hit.get("published_at", ""),
            contract="Stage",
            duration_min=hit.get("contract_duration_minimum"),
            duration_max=hit.get("contract_duration_maximum"),
            summary=hit.get("summary") or "",
            description=description,
            details_fetched=True,
            extra={"remote": hit.get("remote"), "education_level": hit.get("education_level"),
                   "language": hit.get("language"), "salary_min": hit.get("salary_minimum"),
                   "salary_max": hit.get("salary_maximum")},
        ))
    return jobs


def fetch_details(job: Job) -> bool:
    return True
