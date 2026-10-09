"""Offline unit tests for the RX platform adapter (no network)."""

from __future__ import annotations

import pytest

from expo_scraper.adapters.rx_platform import (
    RXPlatformAdapter,
    decode_js_string_literal,
    parse_react_settings,
    seo_friendly_name,
)
from expo_scraper.config import ScrapeConfig


@pytest.mark.parametrize(
    "name, expected",
    [
        ("FaceTec Inc.", "facetec%20inc"),
        ("Thrive Logic", "thrive%20logic"),
        ("2J Antennas USA, Corp", "2j%20antennas%20usa%20corp"),
        ("A&B Co., Ltd.", "ab%20co%20ltd"),
        ("Société Générale", "soci%C3%A9t%C3%A9%20g%C3%A9n%C3%A9rale"),
        ("Hy-Phen_Under", "hy-phen_under"),
        ("", ""),
    ],
)
def test_seo_friendly_name(name, expected):
    assert seo_friendly_name(name) == expected


def test_decode_js_string_literal_handles_hex_unicode_and_slash_escapes():
    raw = r'{\x22a\x22:\x22x-y\x22,\x22u\x22:\x22https:\/\/h\x22}'
    assert decode_js_string_literal(raw) == '{"a":"x-y","u":"https://h"}'


def test_parse_react_settings_extracts_the_json_blob():
    html = (
        '<body data-apigee-clientid="CID"><script>\n'
        '  var reactSettingsShowPlanning = JSON.parse("{\\x22props\\x22:{}}");\n'
        '  var reactSettings = JSON.parse("{\\x22props\\x22:{\\x22context\\x22:{\\x22eventId\\x22:\\x22evt\\u002D1\\x22}}}");\n'
        "</script></body>"
    )
    settings = parse_react_settings(html)
    assert settings["props"]["context"]["eventId"] == "evt-1"


def test_parse_react_settings_missing_raises():
    with pytest.raises(ValueError):
        parse_react_settings("<html></html>")


def _adapter() -> RXPlatformAdapter:
    cfg = ScrapeConfig(name="t", adapter="rx_platform", directory_url="http://x", output_csv="o.csv")
    adapter = RXPlatformAdapter(cfg, session=None, limiter=None)  # type: ignore[arg-type]
    adapter.details_url_format = "https://example.com/dir/exhibitor-details.{0}.html"
    return adapter


HIT = {
    "exhibitorName": "FaceTec Inc.",
    "companyName": "FaceTec",
    "organisationGuid": "org-1",
    "website": "https://facetec.com ",
    "email": "info@facetec.com",
    "standReference": "21139",
    "showObjective": "algolia objective",
    "exhibitorDescription": "algolia description",
    "representedBrands": ["AlgoliaBrand"],
    "exhibitorFilters": {
        "Product Categories": {
            "lvl0": ["1:1: Biometrics"],
            "lvl1": ["2:1: Biometrics > Facial Recognition", "3:2: Biometrics > Liveness Detection"],
        }
    },
}

DETAILS = {
    "organisationId": "org-1",
    "website": "https://facetec.com",
    "contactEmail": "other@facetec.com",
    "socialMedia": [
        {"name": "FACEBOOK", "url": "https://facebook.com/facetec"},
        {"name": "LINKEDIN", "url": "https://www.linkedin.com/company/facetec/"},
    ],
    "multilingual": [
        {"locale": "fr-fr", "displayName": "FaceTec FR", "description": "desc fr",
         "showObjective": "obj fr", "representedBrands": [{"name": "FR"}]},
        {"locale": "en-us", "displayName": "FaceTec Inc.", "description": "desc en\r\n",
         "showObjective": "obj en", "representedBrands": [{"name": "FaceTec"}, {"name": "FaceTec"}]},
    ],
    "filterCategories": [
        {"id": 1, "multilingual": [{"name": "Is your company a diverse-owned business?", "locale": "en-us"}],
         "responses": [{"answerId": 9, "parentId": None, "multilingual": [{"name": "Veteran Owned", "locale": "en-us"}]}]},
        {"id": 2, "multilingual": [{"name": "Product Categories", "locale": "en-us"}],
         "responses": [
             {"answerId": 10, "parentId": 1, "multilingual": [{"name": "Facial Recognition", "locale": "en-us"}]},
             {"answerId": 11, "parentId": 1, "multilingual": [{"name": "Liveness Detection", "locale": "en-us"}]},
             {"answerId": 12, "parentId": 2, "multilingual": [{"name": "Software", "locale": "en-us"}]},
             {"answerId": 13, "parentId": 3, "multilingual": [{"name": "Software", "locale": "en-us"}]},
         ]},
    ],
    "stands": [{"name": "21139"}],
}


def test_map_exhibitor_prefers_detail_page_data_and_builds_source_url():
    ex = _adapter().map_exhibitor(HIT, DETAILS)
    assert ex.company_name == "FaceTec Inc."
    assert ex.website == "https://facetec.com"
    assert ex.email == "info@facetec.com"
    assert ex.stand == "21139"
    assert ex.linkedin_url == "https://www.linkedin.com/company/facetec/"
    assert ex.why_visit_our_stand == "obj en"
    assert ex.description == "desc en"
    assert ex.brands == "FaceTec"
    # Only the "Product Categories" group, de-duplicated, comma separated.
    assert ex.product_categories == "Facial Recognition, Liveness Detection, Software"
    assert ex.source_url == "https://example.com/dir/exhibitor-details.facetec%20inc.org-1.html"


def test_map_exhibitor_falls_back_to_listing_when_details_missing():
    ex = _adapter().map_exhibitor(HIT, None)
    assert ex.linkedin_url == ""
    assert ex.why_visit_our_stand == "algolia objective"
    assert ex.description == "algolia description"
    assert ex.brands == "AlgoliaBrand"
    assert ex.product_categories == "Facial Recognition, Liveness Detection"
    assert ex.source_url.endswith("exhibitor-details.facetec%20inc.org-1.html")


def test_map_exhibitor_without_org_id_has_no_source_url():
    hit = {**HIT, "organisationGuid": ""}
    assert _adapter().map_exhibitor(hit, None).source_url == ""
