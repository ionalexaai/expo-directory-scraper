"""Data model for one exhibitor row and its CSV column mapping."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields


@dataclass
class Exhibitor:
    """One row in the output file. Field order == column order."""

    company_name: str = ""
    website: str = ""
    email: str = ""
    stand: str = ""
    linkedin_url: str = ""
    why_visit_our_stand: str = ""
    description: str = ""
    brands: str = ""
    product_categories: str = ""
    source_url: str = ""

    def as_row(self) -> dict[str, str]:
        return asdict(self)


# Human-readable CSV headers, in the order the job description lists them.
CSV_HEADERS: dict[str, str] = {
    "company_name": "Company Name",
    "website": "Website",
    "email": "Email",
    "stand": "Stand #",
    "linkedin_url": "LinkedIn Company URL",
    "why_visit_our_stand": "Why visit our stand",
    "description": "Description",
    "brands": "Brands we will feature",
    "product_categories": "Product Categories",
    "source_url": "Source URL",
}

FIELD_NAMES: list[str] = [f.name for f in fields(Exhibitor)]
assert list(CSV_HEADERS) == FIELD_NAMES, "CSV_HEADERS must cover every Exhibitor field, in order"
