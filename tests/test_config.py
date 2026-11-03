"""Unit tests for configuration loading and defaults."""

import pytest

from config import Settings, _load_settings
from models import ChangeFlag, Money, Product, Variant


def test_settings_default_values() -> None:
    """Verify that Settings loads canonical default values."""
    s = Settings()
    assert s.DATA_DIR == "./data"
    assert s.SCRAPER_API_KEY is None
    assert s.BASE_URL == "https://eu.store.bambulab.com"
    assert s.RATE_LIMIT_INTERVAL_S == 1.0
    assert s.MAX_CONCURRENCY == 2
    assert s.REQUEST_TIMEOUT_CONNECT_S == 10.0
    assert s.REQUEST_TIMEOUT_READ_S == 20.0
    assert s.MAX_RETRIES == 4


def test_settings_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that MAX_CONCURRENCY and RATE_LIMIT_INTERVAL_S are read from the environment."""
    monkeypatch.setenv("MAX_CONCURRENCY", "4")
    monkeypatch.setenv("RATE_LIMIT_INTERVAL_S", "2.5")
    monkeypatch.setenv("DATA_DIR", "/custom/data")

    loaded = _load_settings()
    assert loaded.MAX_CONCURRENCY == 4
    assert loaded.RATE_LIMIT_INTERVAL_S == 2.5
    assert loaded.DATA_DIR == "/custom/data"


def test_money_validation() -> None:
    """Verify that Money requires integer minor units and 3-letter uppercase currency."""
    m = Money(amount_minor=1299, currency="EUR")
    assert m.amount_minor == 1299
    assert m.currency == "EUR"

    with pytest.raises(ValueError):
        Money(amount_minor=100, currency="euro")

    with pytest.raises(ValueError):
        Money(amount_minor=100, currency="EU")

    with pytest.raises(ValueError):
        Money(amount_minor=100, currency="123")


def test_money_from_decimal_str() -> None:
    """Verify parsing decimal string prices into integer minor units."""
    m = Money.from_decimal_str("349.99", "EUR")
    assert m.amount_minor == 34999
    assert m.currency == "EUR"

    m_zero = Money.from_decimal_str("0.00", "USD")
    assert m_zero.amount_minor == 0
    assert m_zero.currency == "USD"


def test_change_flag_members() -> None:
    """Verify ChangeFlag enum contains exact required members."""
    expected = {
        "IS_NEW_PRODUCT",
        "IS_NEW_VARIANT",
        "IS_NEW_CATEGORY",
        "PRICE_CHANGED",
        "AVAILABILITY_CHANGED",
    }
    actual = {flag.value for flag in ChangeFlag}
    assert actual == expected


def test_model_stubs() -> None:
    """Verify Product and Variant identity stubs."""
    p = Product(product_id=12345)
    assert p.product_id == 12345

    v = Variant(variant_id=67890)
    assert v.variant_id == 67890
