"""Core data models and domain enums for catalog synchronization."""

import re
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, field_validator

# Canonical machine-readable error codes referenced by API surface
ERROR_INVALID_CATEGORY = "invalid_category"
ERROR_UNAUTHORIZED = "unauthorized"
ERROR_RUN_CONFLICT = "run_conflict"
ERROR_RUN_NOT_FOUND = "run_not_found"
ERROR_INTERNAL = "internal_error"

_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")


class ChangeFlag(str, Enum):
    """Event flags emitted by the catalog diff engine."""

    IS_NEW_PRODUCT = "IS_NEW_PRODUCT"
    IS_NEW_VARIANT = "IS_NEW_VARIANT"
    IS_NEW_CATEGORY = "IS_NEW_CATEGORY"
    PRICE_CHANGED = "PRICE_CHANGED"
    AVAILABILITY_CHANGED = "AVAILABILITY_CHANGED"


class Money(BaseModel):
    """Monetary amount represented in integer minor units with a 3-letter currency code."""

    model_config = ConfigDict(extra="ignore")

    amount_minor: int
    currency: str

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        """Validate currency is exactly three uppercase ASCII letters."""
        if not _CURRENCY_PATTERN.match(value):
            raise ValueError(f"Currency must be exactly three uppercase letters, got {value!r}")
        return value

    @classmethod
    def from_decimal_str(cls, price_str: str, currency: str) -> "Money":
        """Parse decimal string price into integer minor units without float precision loss."""
        d = Decimal(price_str)
        minor = int((d * 100).quantize(Decimal("1")))
        return cls(amount_minor=minor, currency=currency)


class Product(BaseModel):
    """Product stub containing identity fields only; full schema defined in U2–U4."""

    model_config = ConfigDict(extra="ignore")

    product_id: int


class Variant(BaseModel):
    """Variant stub containing identity fields only; full schema defined in U2–U4."""

    model_config = ConfigDict(extra="ignore")

    variant_id: int
