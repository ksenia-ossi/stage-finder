import logging
import time

import requests

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

session = requests.Session()
session.headers.update(HEADERS)


def get(url, retries=2, delay=1.0, **kwargs):
    for attempt in range(retries + 1):
        try:
            r = session.get(url, timeout=25, **kwargs)
            if r.status_code == 429 and attempt < retries:
                time.sleep(delay * (attempt + 2))
                continue
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            if attempt >= retries:
                log.warning("GET %s failed: %s", url, e)
                return None
            time.sleep(delay)
    return None
