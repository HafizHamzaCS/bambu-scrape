"""Tests for the WooCommerce export mapping and endpoint (no network)."""

import csv
import io
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import service
import woocommerce as wc
from config import Settings
from main import app

KEY = {"X-API-Key": "test-key"}

PRODUCT: dict[str, Any] = {
    "product_id": 1,
    "handle": "h2c",
    "title": "Bambu Lab H2C",
    "category_key": "printers",
    "url": "https://eu.store.bambulab.com/en/products/h2c",
    "description": "A very capable printer. " * 20,
    "media": [
        {"url": "https://cdn/a.jpg", "type": "image"},
        {"url": "https://cdn/v.mp4", "type": "video"},
        {"url": "https://cdn/b.jpg", "type": "image"},
    ],
    "spec_table": [["Body", "Build Volume", "180*180 <mm>"], ["Nozzle", "Steel"]],
    "variants": [
        {
            "sku": "111",
            "title": "Bambu Lab H2C - AMS Combo / Standard",
            "price_minor": 249900,
            "available": True,
            "image_url": "https://cdn/a.jpg",
        },
        {
            "sku": "222",
            "title": "Bambu Lab H2C - Laser Combo",
            "price_minor": 299900,
            "available": False,
            "image_url": None,
        },
    ],
}
OPTS = wc.ExportOptions()


def test_rows_are_drafts_with_parent_links_and_no_prices_or_stock() -> None:
    rows = wc.to_csv_rows([PRODUCT], OPTS)
    assert [r["Type"] for r in rows] == ["variable", "variation", "variation"]
    assert {r["Published"] for r in rows} == {"-1"}
    # WooCommerce rejects variation rows with an empty catalog visibility
    assert {r["Visibility in catalog"] for r in rows} == {"visible"}
    assert rows[1]["Parent"] == rows[0]["SKU"] == "BL-h2c"
    assert all(not r.get("Regular price") for r in rows)
    assert all("Stock" not in r for r in rows)
    assert rows[0]["Attribute 1 value(s)"] == "AMS Combo / Standard, Laser Combo"
    assert rows[1]["Meta: _bambu_source_price_eur_gross"] == "2499.00"
    assert rows[2]["Meta: _bambu_source_available"] == "0"


def test_include_prices_and_sku_prefix() -> None:
    opts = wc.ExportOptions(include_prices=True, sku_prefix="X-")
    rows = wc.to_csv_rows([PRODUCT], opts)
    assert rows[1]["Regular price"] == "2499.00"
    assert rows[1]["SKU"] == "X-111"
    assert rows[1]["Parent"] == "X-BL-h2c"


def test_images_deduped_images_only_and_limited() -> None:
    assert wc.product_images(PRODUCT, OPTS) == ["https://cdn/a.jpg", "https://cdn/b.jpg"]
    assert wc.product_images(PRODUCT, wc.ExportOptions(max_images=1)) == ["https://cdn/a.jpg"]


def test_description_escapes_html_and_includes_specs() -> None:
    desc = wc.long_description(PRODUCT)
    assert "180*180 &lt;mm&gt;" in desc
    assert "<th>Body - Build Volume</th>" in desc
    assert len(wc.short_description(PRODUCT)) <= 183


def test_duplicate_option_labels_get_disambiguated() -> None:
    product = {
        **PRODUCT,
        "variants": [
            {"sku": "1", "title": "Bambu Lab H2C"},
            {"sku": "2", "title": "Bambu Lab H2C"},
        ],
    }
    assert wc.variant_options(product) == ["Standard", "Standard (2)"]


def test_csv_parses_back_with_importer_columns() -> None:
    reader = csv.DictReader(io.StringIO(wc.render_csv([PRODUCT], OPTS)))
    assert reader.fieldnames == wc.CSV_COLUMNS
    assert len(list(reader)) == 3


def test_rest_payload_shape() -> None:
    (item,) = wc.to_rest_products([PRODUCT], OPTS)
    assert item["status"] == "draft"
    assert item["type"] == "variable"
    assert len(item["variations"]) == 2
    assert item["variations"][1]["image"] is None
    assert item["attributes"][0]["options"] == ["AMS Combo / Standard", "Laser Combo"]


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    cfg = Settings(SCRAPER_API_KEY="test-key", DATA_DIR=str(tmp_path))
    monkeypatch.setattr("main.settings", cfg)
    monkeypatch.setattr("service.settings", cfg)
    monkeypatch.setattr(service, "load_catalog", lambda category: [PRODUCT])
    return TestClient(app)


def test_export_endpoint_csv_json_and_auth(client: TestClient) -> None:
    assert client.get("/export/woocommerce").status_code == 401
    resp = client.get("/export/woocommerce", headers=KEY)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"]
    body = client.get("/export/woocommerce?format=json", headers=KEY).json()
    assert body["meta"]["count"] == 1
    assert client.get("/export/woocommerce?format=xml", headers=KEY).status_code == 422
    assert client.get("/export/woocommerce?category=bundles", headers=KEY).status_code == 400


def test_commas_in_option_labels_are_escaped_for_the_importer() -> None:
    product = {
        **PRODUCT,
        "variants": [{"sku": "1", "title": "Bambu Lab H2C - Red, Large", "price_minor": 100}],
    }
    rows = wc.to_csv_rows([product], OPTS)
    assert rows[0]["Attribute 1 value(s)"] == "Red\\, Large"
    assert rows[1]["Attribute 1 value(s)"] == "Red\\, Large"
