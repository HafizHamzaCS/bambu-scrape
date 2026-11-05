"""Map scraped Bambu catalog products to WooCommerce import formats (CSV and REST JSON).

Project rules honoured here (see 03_WordPress_Plugins_and_Custom_Modules.md):
- Imports create DRAFT products only; nothing is published automatically.
- Merit is master for stock and selling prices, so stock is never exported and the
  regular price is left blank unless ``include_prices`` is explicitly requested.
- The Bambu source price (VAT-inclusive EU store price) is always kept as meta
  for advisory comparison.
- Products are matched by SKU; variation SKUs are the Bambu SKU ids with an optional prefix.
"""

import csv
import html
import io
import json
from dataclasses import dataclass
from typing import Any

CATEGORY_NAMES = {"printers": "3D Printers", "filaments": "Filaments"}
ATTRIBUTE_NAME = "Option"

CSV_COLUMNS = [
    "ID",
    "Type",
    "SKU",
    "Name",
    "Published",
    "Is featured?",
    "Visibility in catalog",
    "Short description",
    "Description",
    "Tax status",
    "In stock?",
    "Stock",
    "Regular price",
    "Categories",
    "Images",
    "Parent",
    "Attribute 1 name",
    "Attribute 1 value(s)",
    "Attribute 1 visible",
    "Attribute 1 global",
    "Meta: _bambu_source_url",
    "Meta: _bambu_source_product_id",
    "Meta: _bambu_source_price_eur_gross",
    "Meta: _bambu_source_available",
    "Meta: _bambu_spec_table",
]


@dataclass(frozen=True)
class ExportOptions:
    """Knobs for the export."""

    include_prices: bool = False
    sku_prefix: str = ""
    max_images: int = 10


def _money(minor: int | None) -> str:
    return "" if minor is None else f"{minor / 100:.2f}"


def parent_sku(product: dict[str, Any], opts: ExportOptions) -> str:
    """SKU of the variable (parent) product."""
    return f"{opts.sku_prefix}BL-{product['handle']}"


def product_images(product: dict[str, Any], opts: ExportOptions) -> list[str]:
    """Unique image URLs: variant images first (they show the product), then the gallery."""
    urls: list[str] = []
    candidates = [v.get("image_url") for v in product.get("variants") or []]
    candidates += [m.get("url") for m in product.get("media") or [] if m.get("type") == "image"]
    for url in candidates:
        if url and url not in urls:
            urls.append(url)
    return urls[: opts.max_images]


def variant_options(product: dict[str, Any]) -> list[str]:
    """Derive a unique option label per variant from its title (Bambu has no option fields)."""
    prefix = f"{product['title']} - "
    labels: list[str] = []
    for v in product.get("variants") or []:
        title = str(v.get("title") or "")
        label = title[len(prefix) :] if title.startswith(prefix) else title
        label = label.strip()
        if not label or label == product["title"]:
            label = "Standard"
        if label in labels:
            label = f"{label} ({v.get('sku')})"
        labels.append(label)
    return labels


def _csv_list_item(value: str) -> str:
    """WooCommerce's importer splits list fields on commas; escape literal ones."""
    return value.replace(",", "\\,")


def spec_table_html(spec_table: list[list[str]]) -> str:
    """Render the scraped specification rows as an HTML table."""
    if not spec_table:
        return ""
    rows = []
    for row in spec_table:
        cells = [html.escape(str(c)) for c in row if str(c).strip()]
        if len(cells) >= 3:
            label, value = f"{cells[0]} - {cells[1]}", ", ".join(cells[2:])
        elif len(cells) == 2:
            label, value = cells
        elif cells:
            label, value = cells[0], ""
        else:
            continue
        rows.append(f"<tr><th>{label}</th><td>{value}</td></tr>")
    return "<h3>Technical specifications</h3><table><tbody>" + "".join(rows) + "</tbody></table>"


def long_description(product: dict[str, Any]) -> str:
    """Product description followed by the specification table."""
    desc = html.escape(product.get("description") or "").replace("\n", "<br>")
    return (f"<p>{desc}</p>" if desc else "") + spec_table_html(product.get("spec_table") or [])


def short_description(product: dict[str, Any], limit: int = 180) -> str:
    """First ~180 characters of the description, cut at a word boundary."""
    text = " ".join((product.get("description") or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "..."


def to_csv_rows(products: list[dict[str, Any]], opts: ExportOptions) -> list[dict[str, str]]:
    """One 'variable' row per product followed by one 'variation' row per variant."""
    rows: list[dict[str, str]] = []
    for p in products:
        variants = p.get("variants") or []
        if not variants:
            continue
        labels = variant_options(p)
        psku = parent_sku(p, opts)
        prices = [v["price_minor"] for v in variants if v.get("price_minor") is not None]
        rows.append(
            {
                "Type": "variable",
                "SKU": psku,
                "Name": p["title"],
                "Published": "-1",
                "Is featured?": "0",
                "Visibility in catalog": "visible",
                "Short description": short_description(p),
                "Description": long_description(p),
                "Tax status": "taxable",
                "Categories": CATEGORY_NAMES.get(p.get("category_key", ""), ""),
                "Images": ", ".join(product_images(p, opts)),
                "Attribute 1 name": ATTRIBUTE_NAME,
                "Attribute 1 value(s)": ", ".join(_csv_list_item(x) for x in labels),
                "Attribute 1 visible": "1",
                "Attribute 1 global": "0",
                "Meta: _bambu_source_url": p.get("url") or "",
                "Meta: _bambu_source_product_id": str(p.get("product_id") or ""),
                "Meta: _bambu_source_price_eur_gross": _money(min(prices) if prices else None),
                "Meta: _bambu_spec_table": json.dumps(
                    p.get("spec_table") or [], ensure_ascii=False
                ),
            }
        )
        for v, label in zip(variants, labels, strict=True):
            rows.append(
                {
                    "Type": "variation",
                    "SKU": f"{opts.sku_prefix}{v['sku']}",
                    "Name": f"{p['title']} - {label}",
                    "Published": "-1",
                    "Tax status": "taxable",
                    "Regular price": _money(v.get("price_minor")) if opts.include_prices else "",
                    "Images": v.get("image_url") or "",
                    "Parent": psku,
                    "Attribute 1 name": ATTRIBUTE_NAME,
                    "Attribute 1 value(s)": _csv_list_item(label),
                    "Attribute 1 global": "0",
                    "Meta: _bambu_source_url": p.get("url") or "",
                    "Meta: _bambu_source_price_eur_gross": _money(v.get("price_minor")),
                    "Meta: _bambu_source_available": "1" if v.get("available") else "0",
                }
            )
    return rows


def render_csv(products: list[dict[str, Any]], opts: ExportOptions) -> str:
    """CSV text in the WooCommerce product importer format."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, extrasaction="raise", lineterminator="\n")
    writer.writeheader()
    for row in to_csv_rows(products, opts):
        writer.writerow({col: row.get(col, "") for col in CSV_COLUMNS})
    return buf.getvalue()


def to_rest_products(products: list[dict[str, Any]], opts: ExportOptions) -> list[dict[str, Any]]:
    """WooCommerce REST v3 payloads (POST /wp-json/wc/v3/products, then /variations)."""
    out: list[dict[str, Any]] = []
    for p in products:
        variants = p.get("variants") or []
        if not variants:
            continue
        labels = variant_options(p)
        prices = [v["price_minor"] for v in variants if v.get("price_minor") is not None]
        out.append(
            {
                "type": "variable",
                "status": "draft",
                "sku": parent_sku(p, opts),
                "name": p["title"],
                "short_description": short_description(p),
                "description": long_description(p),
                "categories": [{"name": CATEGORY_NAMES.get(p.get("category_key", ""), "")}],
                "images": [{"src": u} for u in product_images(p, opts)],
                "attributes": [
                    {"name": ATTRIBUTE_NAME, "visible": True, "variation": True, "options": labels}
                ],
                "meta_data": [
                    {"key": "_bambu_source_url", "value": p.get("url")},
                    {"key": "_bambu_source_product_id", "value": str(p.get("product_id") or "")},
                    {
                        "key": "_bambu_source_price_eur_gross",
                        "value": _money(min(prices) if prices else None),
                    },
                    {"key": "_bambu_spec_table", "value": json.dumps(p.get("spec_table") or [])},
                ],
                "variations": [
                    {
                        "sku": f"{opts.sku_prefix}{v['sku']}",
                        "status": "private",
                        "regular_price": _money(v.get("price_minor"))
                        if opts.include_prices
                        else "",
                        "attributes": [{"name": ATTRIBUTE_NAME, "option": label}],
                        "image": {"src": v["image_url"]} if v.get("image_url") else None,
                        "meta_data": [
                            {
                                "key": "_bambu_source_price_eur_gross",
                                "value": _money(v.get("price_minor")),
                            },
                            {"key": "_bambu_source_available", "value": bool(v.get("available"))},
                        ],
                    }
                    for v, label in zip(variants, labels, strict=True)
                ],
            }
        )
    return out
