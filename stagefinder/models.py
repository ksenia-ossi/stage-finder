from dataclasses import dataclass, field, asdict
from typing import Optional
import re
import unicodedata


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return text.strip("-")


@dataclass
class Job:
    source: str
    source_id: str
    title: str
    company: str
    url: str
    location: str = ""
    posted_at: str = ""
    contract: str = ""
    duration_min: Optional[int] = None
    duration_max: Optional[int] = None
    summary: str = ""
    description: str = ""
    details_fetched: bool = False
    extra: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.source}:{self.source_id}"

    @property
    def dedupe_key(self) -> str:
        return f"{slugify(self.company)}|{slugify(self.title)}"

    @property
    def text(self) -> str:
        return " ".join(filter(None, [self.title, self.summary, self.description]))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["key"] = self.key
        d["dedupe_key"] = self.dedupe_key
        return d
