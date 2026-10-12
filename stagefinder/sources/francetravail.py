"""France Travail (ex Pôle emploi) official API. Optional: needs free credentials from
https://francetravail.io (set FT_CLIENT_ID / FT_CLIENT_SECRET env vars)."""
import logging
import os

import requests

from ..models import Job

log = logging.getLogger(__name__)
NAME = "francetravail"
TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire"
SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"


def enabled() -> bool:
    return bool(os.environ.get("FT_CLIENT_ID") and os.environ.get("FT_CLIENT_SECRET"))


def _token() -> str | None:
    try:
        r = requests.post(TOKEN_URL, data={
            "grant_type": "client_credentials",
            "client_id": os.environ["FT_CLIENT_ID"],
            "client_secret": os.environ["FT_CLIENT_SECRET"],
            "scope": "api_offresdemploiv2 o2dsoffre",
        }, timeout=25)
        r.raise_for_status()
        return r.json().get("access_token")
    except (requests.RequestException, ValueError) as e:
        log.warning("France Travail auth failed: %s", e)
        return None


def search(query: str, region: str = "11") -> list[Job]:
    if not enabled():
        return []
    token = _token()
    if not token:
        return []
    try:
        r = requests.get(SEARCH_URL, params={"motsCles": query, "region": region, "range": "0-149"},
                         headers={"Authorization": f"Bearer {token}"}, timeout=25)
        if r.status_code == 204:
            return []
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError) as e:
        log.warning("France Travail search failed: %s", e)
        return []
    jobs = []
    for o in data.get("resultats", []):
        jobs.append(Job(
            source=NAME,
            source_id=o.get("id", ""),
            title=o.get("intitule", ""),
            company=(o.get("entreprise") or {}).get("nom", ""),
            url=(o.get("origineOffre") or {}).get("urlOrigine") or f"https://candidat.francetravail.fr/offres/recherche/detail/{o.get('id')}",
            location=(o.get("lieuTravail") or {}).get("libelle", ""),
            posted_at=o.get("dateCreation", ""),
            contract=o.get("typeContratLibelle", ""),
            description=o.get("description", ""),
            details_fetched=True,
        ))
    return jobs


def fetch_details(job: Job) -> bool:
    return True
