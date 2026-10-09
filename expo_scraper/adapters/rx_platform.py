"""Adapter for exhibitor directories built on the RX (Reed Exhibitions) show platform.

Sites on this platform (ISC West, ISC East and many other RX shows) render the
directory client-side from two public data sources:

* an Algolia index  -> the listing (name, website, email, stand, description, ...)
* a public GraphQL API on api.reedexpo.com -> the detail page (social links, brands,
  full category list that sits behind "Show all categories")

Every id and key needed to call those two sources is embedded in the directory
page's HTML (`var reactSettings = JSON.parse("...")`), so the adapter discovers
them automatically. Any value can still be pinned in the YAML config under `rx:`.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any
from urllib.parse import quote, urlencode

from expo_scraper.adapters.base import DirectoryAdapter
from expo_scraper.models import Exhibitor

log = logging.getLogger(__name__)

_REACT_SETTINGS_RE = re.compile(r'var\s+reactSettings\s*=\s*JSON\.parse\("(.*?)"\);', re.S)
_CLIENT_ID_RE = re.compile(r'data-apigee-clientid="([^"]+)"')
_SAFE_ID_RE = re.compile(r"^[\w.-]+$")

# Mirrors the site's own query for the exhibitor detail page, trimmed to what we export.
_DETAILS_QUERY = """{
  exhibitingOrganisation(eventEditionId: %s, organisationId: %s) {
    id
    organisationId
    companyName
    contactEmail
    website
    socialMedia { url name }
    multilingual {
      locale
      displayName
      description
      showObjective
      representedBrands { name }
    }
    filterCategories {
      id
      multilingual { name locale }
      responses { answerId parentId multilingual { name locale } }
    }
    stands { name }
  }
}"""


def decode_js_string_literal(raw: str) -> str:
    """Decode the body of a JS double-quoted string literal (as emitted inside JSON.parse("..."))."""
    raw = re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: "\\u00" + m.group(1), raw)
    raw = raw.replace("\\'", "'")
    return json.loads('"' + raw + '"')


def parse_react_settings(html: str) -> dict[str, Any]:
    """Return the `reactSettings` object the directory page hands to its React app."""
    match = _REACT_SETTINGS_RE.search(html)
    if not match:
        raise ValueError("could not find `var reactSettings = JSON.parse(...)` in the directory page")
    return json.loads(decode_js_string_literal(match.group(1)))


def seo_friendly_name(name: str) -> str:
    """Port of the site's getSEOFriendlyName(): strip punctuation, lowercase, URL-encode.

    JS source: name.replace(/[^\\w\\s\\d\\p{L}-]/gu, "") then encodeURIComponent(lower).
    """
    if not name:
        return ""
    kept = "".join(
        ch for ch in name
        if ch.isalpha() or ch.isdigit() or ch == "_" or ch == "-" or ch.isspace()
    )
    return quote(kept.lower(), safe="-_.!~*'()")


def _clean(text: Any) -> str:
    if text is None:
        return ""
    text = str(text).replace("\r\n", "\n").replace("\r", "\n")
    return text.strip()


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.casefold()
        if item and key not in seen:
            seen.add(key)
            out.append(item)
    return out


class RXPlatformAdapter(DirectoryAdapter):
    name = "rx_platform"

    # Filled by discover() (or overridden from config `rx:`).
    algolia_app_id: str = ""
    algolia_api_key: str = ""
    event_id: str = ""
    event_edition_id: str = ""
    api_base_url: str = "https://api.reedexpo.com/"
    client_id: str = ""
    details_url_format: str = ""
    category_filter_name: str = "Product Categories"
    hits_per_page: int = 1000

    # ---- discovery ---------------------------------------------------------------

    def discover(self) -> None:
        opts = dict(self.config.adapter_options.get("rx") or {})
        self.category_filter_name = opts.pop("category_filter_name", self.category_filter_name)
        self.hits_per_page = int(opts.pop("hits_per_page", self.hits_per_page))

        log.info("Fetching directory page %s", self.config.directory_url)
        self.limiter.wait()
        resp = self.session.get(self.config.directory_url, timeout=30, headers={"Accept": "text/html"})
        resp.raise_for_status()
        html = resp.text

        settings = parse_react_settings(html)
        props = settings.get("props", {})
        context = props.get("context", {})
        algolia = props.get("algoliaConfig", {})
        navigation = props.get("navigation", {})

        self.algolia_app_id = algolia.get("appId", "")
        self.algolia_api_key = algolia.get("apiKey", "")
        self.event_id = context.get("eventId", "")
        self.event_edition_id = context.get("eventEditionId", "")
        self.api_base_url = props.get("baseApiUrl") or self.api_base_url
        self.details_url_format = navigation.get("exhibitorPublicDetailsUrlFormat", "")
        client_match = _CLIENT_ID_RE.search(html)
        self.client_id = client_match.group(1) if client_match else ""
        if context.get("interfaceLocale") and not self.config.adapter_options.get("locale"):
            # Site locale wins over the config default unless the user pinned one.
            self.config.locale = str(context["interfaceLocale"]).lower()

        # Config overrides anything discovered (useful if a site changes markup).
        for key, value in opts.items():
            if not hasattr(self, key):
                raise ValueError(f"unknown rx option '{key}'")
            setattr(self, key, value)

        missing = [
            k for k in ("algolia_app_id", "algolia_api_key", "event_id", "event_edition_id",
                        "client_id", "details_url_format")
            if not getattr(self, k)
        ]
        if missing:
            raise ValueError(f"discovery incomplete, set these under `rx:` in the config: {missing}")
        log.info("Discovered RX settings: %s", self.describe())

    def describe(self) -> dict[str, Any]:
        return {
            "event_name": "",
            "event_id": self.event_id,
            "event_edition_id": self.event_edition_id,
            "algolia_index": self.algolia_index,
            "api_base_url": self.api_base_url,
            "details_url_format": self.details_url_format,
            "locale": self.config.locale,
        }

    @property
    def algolia_index(self) -> str:
        return f"{self.event_id}-index"

    # ---- listing (Algolia) -------------------------------------------------------

    def list_exhibitors(self) -> list[dict[str, Any]]:
        url = f"https://{self.algolia_app_id}-dsn.algolia.net/1/indexes/{self.algolia_index}/query"
        headers = {
            "X-Algolia-API-Key": self.algolia_api_key,
            "X-Algolia-Application-Id": self.algolia_app_id,
            "Content-Type": "application/json",
        }
        hits: list[dict[str, Any]] = []
        page = 0
        while True:
            params = urlencode({
                "query": "",
                "hitsPerPage": self.hits_per_page,
                "page": page,
                "filters": f"eventEditionId:{self.event_edition_id} AND recordType:exhibitor",
                "attributesToHighlight": "[]",
            })
            self.limiter.wait()
            resp = self.session.post(url, json={"params": params}, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            hits.extend(data.get("hits", []))
            nb_pages = int(data.get("nbPages", 1))
            log.info("Algolia page %d/%d -> %d hits so far (nbHits=%s)",
                     page + 1, nb_pages, len(hits), data.get("nbHits"))
            page += 1
            if page >= nb_pages:
                break
        hits.sort(key=lambda h: (h.get("sortAlias") or h.get("exhibitorName") or "").strip().casefold())
        return hits

    # ---- details (GraphQL) -------------------------------------------------------

    def fetch_details(self, organisation_id: str) -> dict[str, Any] | None:
        if not _SAFE_ID_RE.match(organisation_id) or not _SAFE_ID_RE.match(self.event_edition_id):
            raise ValueError(f"refusing to interpolate suspicious id: {organisation_id!r}")
        query = _DETAILS_QUERY % (json.dumps(self.event_edition_id), json.dumps(organisation_id))
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-ClientId": self.client_id,
            "X-CorrelationId": str(uuid.uuid4()),
        }
        self.limiter.wait()
        resp = self.session.post(
            self.api_base_url.rstrip("/") + "/graphql/",
            json={"query": query, "variables": None},
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("errors"):
            log.warning("GraphQL errors for %s: %s", organisation_id, payload["errors"])
        return (payload.get("data") or {}).get("exhibitingOrganisation")

    def build_exhibitor(self, record: dict[str, Any]) -> Exhibitor:
        org_id = record.get("organisationGuid") or ""
        details: dict[str, Any] | None = None
        if org_id:
            try:
                details = self.fetch_details(org_id)
            except Exception as exc:  # noqa: BLE001 - one bad page must not kill the run
                log.warning("Detail fetch failed for %s (%s): %s",
                            record.get("exhibitorName"), org_id, exc)
        return self.map_exhibitor(record, details)

    # ---- mapping (pure, unit-testable) -------------------------------------------

    def map_exhibitor(self, hit: dict[str, Any], details: dict[str, Any] | None) -> Exhibitor:
        details = details or {}
        ml = self._pick_locale(details.get("multilingual") or [])

        name = _clean(hit.get("exhibitorName") or hit.get("companyName") or ml.get("displayName"))
        org_id = hit.get("organisationGuid") or details.get("organisationId") or ""

        brands = [b.get("name", "") for b in (ml.get("representedBrands") or [])]
        if not brands:
            brands = list(hit.get("representedBrands") or [])

        categories = self._categories_from_details(details)
        if not categories:
            categories = self._categories_from_hit(hit)

        stand = _clean(hit.get("standReference"))
        if not stand:
            stand = ", ".join(_clean(s.get("name")) for s in details.get("stands") or [] if s.get("name"))

        return Exhibitor(
            company_name=name,
            website=_clean(hit.get("website") or details.get("website")),
            email=_clean(hit.get("email") or details.get("contactEmail")),
            stand=stand,
            linkedin_url=self._social(details, "LINKEDIN"),
            why_visit_our_stand=_clean(ml.get("showObjective") or hit.get("showObjective")),
            description=_clean(ml.get("description") or hit.get("exhibitorDescription")),
            brands=", ".join(_dedupe([_clean(b) for b in brands])),
            product_categories=", ".join(categories),
            source_url=self.detail_url(name, org_id),
        )

    def detail_url(self, display_name: str, organisation_id: str) -> str:
        if not organisation_id:
            return ""
        slug = seo_friendly_name(display_name)
        token = f"{slug}.{organisation_id}" if slug else organisation_id
        return self.details_url_format.replace("{0}", token)

    def _pick_locale(self, entries: list[dict[str, Any]]) -> dict[str, Any]:
        want = self.config.locale
        for entry in entries:
            if str(entry.get("locale", "")).lower() == want:
                return entry
        return entries[0] if entries else {}

    def _local_name(self, multilingual: list[dict[str, Any]]) -> str:
        return _clean(self._pick_locale(multilingual).get("name"))

    @staticmethod
    def _social(details: dict[str, Any], network: str) -> str:
        for link in details.get("socialMedia") or []:
            if str(link.get("name", "")).upper() == network and link.get("url"):
                return _clean(link["url"])
        return ""

    def _categories_from_details(self, details: dict[str, Any]) -> list[str]:
        want = self.category_filter_name.casefold()
        names: list[str] = []
        for group in details.get("filterCategories") or []:
            if self._local_name(group.get("multilingual") or []).casefold() != want:
                continue
            for response in group.get("responses") or []:
                names.append(self._local_name(response.get("multilingual") or []))
        return _dedupe(names)

    def _categories_from_hit(self, hit: dict[str, Any]) -> list[str]:
        """Fallback: Algolia stores 'id:order: Parent > Leaf' strings under exhibitorFilters."""
        groups = hit.get("exhibitorFilters") or {}
        group = groups.get(self.category_filter_name) or {}
        leaves: list[str] = []
        for entry in group.get("lvl1") or []:
            label = entry.split(":", 2)[-1]
            leaves.append(_clean(label.split(">")[-1]))
        return _dedupe(leaves)
