"""Bambu Lab EU Storefront Catalog Scraper.

Standalone script to extract structured catalog data (3D Printers & Filaments)
from https://eu.store.bambulab.com with single-page depth, full technical
specifications, complete variant combinations, and high-resolution media galleries.

Usage:
    python scraper.py --category printers --output printers.json
    python scraper.py --category filaments --output filaments.json
    python scraper.py --category all --output catalog.json
"""

import argparse
import json
import logging
import re
import sys
import time
import urllib.request
from typing import Any, cast

from bs4 import BeautifulSoup  # type: ignore[import-untyped]

# Configure logging to stderr so JSON stdout can be piped cleanly
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stderr,
)
logger = logging.getLogger("bambu_scraper")

# Storefront Configuration
BASE_URL = "https://eu.store.bambulab.com"
CATEGORY_HANDLES = {
    "printers": "3d-printer",
    "filaments": "bambu-lab-3d-printer-filament",
}

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}


# =====================================================================
# HTTP FETCHING & POLITE RETRY LOGIC
# =====================================================================


def fetch_url(url: str, delay_s: float = 1.0, max_retries: int = 3) -> str:
    """Fetch HTML content with rate limiting, GeoIP bypass, and retries.

    Args:
        url: Target storefront URL.
        delay_s: Delay in seconds to wait before each request.
        max_retries: Maximum number of retry attempts on network error.

    Returns:
        Decoded HTML string of the target page.
    """
    # Ensure GeoIP bypass parameter is present
    if "skr=yes" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}skr=yes"

    time.sleep(delay_s)
    logger.info("Fetching: %s", url)

    req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=20.0) as resp:
                content: str = resp.read().decode("utf-8", errors="ignore")
                return content
        except Exception as e:
            last_error = e
            logger.warning("Attempt %d failed for %s: %s", attempt, url, e)
            if attempt < max_retries:
                time.sleep(2.0 * attempt)

    raise RuntimeError(f"Failed to fetch {url} after {max_retries} attempts: {last_error}")


# =====================================================================
# FILTERING & PARSING HELPERS
# =====================================================================


def is_refurbished(title: str, handle: str) -> bool:
    """Check if an item is refurbished, renewed, or recertified."""
    keywords = ["refurbished", "renewed", "recertified", "b-stock", "open-box"]
    text = f"{title} {handle}".lower()
    return any(kw in text for kw in keywords)


def extract_collection_products(html: str) -> list[dict[str, Any]]:
    """Extract product summary entries from a category collection page.

    The Next.js storefront embeds initial category state inside a 'productList'
    JSON array in the page stream.
    """
    idx = html.find('productList":')
    if idx == -1:
        idx = html.find('productList\\":')
    if idx == -1:
        logger.error("Could not find productList in collection HTML.")
        return []

    start = html.find("[", idx)
    if start == -1:
        return []

    count = 0
    in_str = False
    escape = False
    end = -1

    for i in range(start, len(html)):
        ch = html[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if not in_str:
            if ch == "[":
                count += 1
            elif ch == "]":
                count -= 1
                if count == 0:
                    end = i + 1
                    break

    if end == -1:
        return []

    raw_arr = html[start:end]
    try:
        clean_arr = raw_arr.encode("utf-8").decode("unicode_escape")
        return cast(list[dict[str, Any]], json.loads(clean_arr))
    except Exception:
        clean_arr = raw_arr.replace('\\"', '"').replace("\\\\", "\\")
        return cast(list[dict[str, Any]], json.loads(clean_arr))


def extract_schema_ld(soup: BeautifulSoup) -> dict[str, Any] | None:
    """Extract Schema.org ProductGroup JSON-LD structured data."""
    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
            if data.get("@type") == "ProductGroup":
                return cast(dict[str, Any], data)
            if isinstance(data, list):
                for item in data:
                    if item.get("@type") == "ProductGroup":
                        return cast(dict[str, Any], item)
        except Exception:
            continue
    return None


def extract_spec_table(soup: BeautifulSoup) -> list[list[str]]:
    """Extract technical parameters and hardware comparison from the HTML table."""
    spec_rows: list[list[str]] = []
    table = soup.find("table")
    if not table:
        return spec_rows

    for row in table.find_all("tr"):
        cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
        if cells and any(cells):
            spec_rows.append(cells)
    return spec_rows


def extract_media_gallery(html: str) -> list[dict[str, str]]:
    """Extract high-resolution media gallery assets from Next.js RSC components."""
    media_list: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    # Search for CDN gallery URLs in mediaFiles arrays
    matches = re.findall(
        r'https://store\.bblcdn\.eu/s[0-9]+/default/[a-zA-Z0-9]+/[^"\'\s]+\.(?:jpg|jpeg|png|webp)',
        html,
        re.I,
    )
    for url in matches:
        # Strip query strings or image transformation parameters to keep full resolution
        clean_url = url.split("__op__")[0].split("?")[0]
        if clean_url not in seen_urls and not clean_url.endswith("logo.png"):
            seen_urls.add(clean_url)
            filename = clean_url.split("/")[-1]
            media_list.append(
                {
                    "id": filename,
                    "url": clean_url,
                    "type": "image",
                }
            )
    return media_list


# =====================================================================
# MAIN SCRAPING LOGIC STARTS HERE
# =====================================================================


def scrape_product_detail(
    handle: str,
    category_key: str,
    summary_item: dict[str, Any] | None = None,
    delay_s: float = 1.0,
) -> dict[str, Any] | None:
    """Scrape full single-page depth for a product URL.

    Pulls Schema.org identity & variants, HTML spec table, and full media gallery.

    Args:
        handle: Product URL handle / slug (e.g., 'a1-mini' or 'pla-basic-filament').
        category_key: Category identifier ('printers' or 'filaments').
        summary_item: Optional summary item from collection listing.
        delay_s: Politeness delay between requests.

    Returns:
        Structured product dictionary, or None if skipped (e.g. refurbished).
    """
    url = f"{BASE_URL}/en/products/{handle}?skr=yes"
    html = fetch_url(url, delay_s=delay_s)
    soup = BeautifulSoup(html, "lxml")

    # Tier 1: Schema.org structured data
    ld_data = extract_schema_ld(soup)

    if ld_data and ld_data.get("name"):
        title = str(ld_data["name"])
    elif summary_item and summary_item.get("name"):
        title = str(summary_item["name"])
    else:
        title = handle

    if is_refurbished(title, handle):
        logger.info("Skipping refurbished product: %s (%s)", title, handle)
        return None

    # Tier 2: HTML Technical Specification Table
    spec_table = extract_spec_table(soup)

    # Tier 3: Media Gallery
    media_gallery = extract_media_gallery(html)

    # Extract Variants & Pricing
    variants: list[dict[str, Any]] = []
    if ld_data and "hasVariant" in ld_data:
        for v in ld_data.get("hasVariant", []):
            sku = str(v.get("sku", ""))
            offers = v.get("offers", {})
            price = offers.get("price", 0)
            strikethrough = None
            price_spec = offers.get("priceSpecification")
            if isinstance(price_spec, dict):
                strikethrough = price_spec.get("price")

            # Store monetary amounts in integer minor units (cents)
            price_minor = int(round(float(price) * 100)) if price else None
            compare_minor = int(round(float(strikethrough) * 100)) if strikethrough else None

            is_in_stock = "InStock" in str(offers.get("availability", ""))

            variants.append(
                {
                    "variant_id": int(sku) if sku.isdigit() else sku,
                    "title": v.get("name", title),
                    "sku": sku,
                    "price_minor": price_minor,
                    "compare_at_minor": compare_minor,
                    "currency": offers.get("priceCurrency", "EUR"),
                    "available": is_in_stock,
                    "image_url": v.get("image"),
                }
            )

    # Fallback to summary variants if JSON-LD variants are absent
    if not variants and summary_item:
        price = summary_item.get("lowerPrice") or summary_item.get("price")
        price_minor = int(round(float(price) * 100)) if price else None
        variants.append(
            {
                "variant_id": summary_item.get("id"),
                "title": title,
                "sku": summary_item.get("lowerPriceSkuId") or str(summary_item.get("id")),
                "price_minor": price_minor,
                "compare_at_minor": None,
                "currency": summary_item.get("currency", "EUR"),
                "available": True,
                "image_url": summary_item.get("mediaFiles", [None])[0],
            }
        )

    product_id_raw = None
    if ld_data and ld_data.get("productGroupID"):
        product_id_raw = ld_data["productGroupID"]
    elif summary_item and summary_item.get("id"):
        product_id_raw = summary_item["id"]

    product_id = (
        int(product_id_raw) if product_id_raw and str(product_id_raw).isdigit() else product_id_raw
    )

    return {
        "product_id": product_id,
        "handle": handle,
        "title": title,
        "category_key": category_key,
        "vendor": "Bambu Lab",
        "url": f"{BASE_URL}/en/products/{handle}",
        "description": ld_data.get("description") if ld_data else None,
        "seo_title": soup.title.string.strip() if soup.title and soup.title.string else None,
        "media": media_gallery,
        "spec_table": spec_table,
        "variants": variants,
        "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def scrape_category(
    category_key: str,
    limit: int | None = None,
    delay_s: float = 1.0,
) -> list[dict[str, Any]]:
    """Scrape all products belonging to a specific category.

    Args:
        category_key: 'printers' or 'filaments'.
        limit: Optional maximum number of products to scrape.
        delay_s: Politeness delay between requests.

    Returns:
        List of detailed product dictionaries.
    """
    handle = CATEGORY_HANDLES.get(category_key)
    if not handle:
        raise ValueError(f"Unknown category '{category_key}'. Must be 'printers' or 'filaments'.")

    collection_url = f"{BASE_URL}/en/collections/{handle}?skr=yes"
    logger.info("=== Scraping Category '%s' from %s ===", category_key, collection_url)

    html = fetch_url(collection_url, delay_s=delay_s)
    summary_items = extract_collection_products(html)
    logger.info("Found %d products in collection '%s'", len(summary_items), category_key)

    if limit:
        summary_items = summary_items[:limit]

    products: list[dict[str, Any]] = []
    for idx, item in enumerate(summary_items, start=1):
        seo_code = item.get("seoCode")
        if not seo_code:
            continue

        logger.info("[%d/%d] Scraping details for '%s'...", idx, len(summary_items), seo_code)
        try:
            prod_detail = scrape_product_detail(
                handle=seo_code,
                category_key=category_key,
                summary_item=item,
                delay_s=delay_s,
            )
            if prod_detail:
                products.append(prod_detail)
        except Exception as e:
            logger.error("Error scraping product '%s': %s", seo_code, e)

    logger.info("Finished category '%s': %d products extracted", category_key, len(products))
    return products


def scrape_all(limit: int | None = None, delay_s: float = 1.0) -> dict[str, list[dict[str, Any]]]:
    """Scrape all supported v1 categories (3D Printers and Filaments)."""
    return {cat: scrape_category(cat, limit=limit, delay_s=delay_s) for cat in CATEGORY_HANDLES}


# =====================================================================
# CLI RUNNER & DATA EXPORT
# =====================================================================


def main() -> None:
    """CLI entry point for running standalone scraper."""
    parser = argparse.ArgumentParser(
        description="Bambu Lab EU Catalog Scraper - Extract products, specs, variants & media."
    )
    parser.add_argument(
        "--category",
        choices=["printers", "filaments", "all"],
        default="printers",
        help="Category to scrape (default: printers)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of products to scrape (useful for testing)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay in seconds between requests (politeness rate limiter, default: 1.0)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output JSON file path (prints to stdout if omitted)",
    )

    args = parser.parse_args()

    data: dict[str, Any] | list[dict[str, Any]]
    if args.category == "all":
        data = scrape_all(limit=args.limit, delay_s=args.delay)
    else:
        data = scrape_category(args.category, limit=args.limit, delay_s=args.delay)

    json_str = json.dumps(data, indent=2, ensure_ascii=False)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json_str)
        logger.info("Successfully exported data to '%s'", args.output)
    else:
        print(json_str)


if __name__ == "__main__":
    main()
