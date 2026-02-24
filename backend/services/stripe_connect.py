"""Helpers for Stripe Connect feature flags and fee calculations."""
from __future__ import annotations

import os
from typing import Any, Dict


def _is_true(value: str | None) -> bool:
    if not value:
        return False
    return value.lower() in ("true", "1", "yes", "on")


def is_stripe_connect_enabled() -> bool:
    return _is_true(os.environ.get("STRIPE_CONNECT_ENABLED"))


def get_platform_fee_bps(shop: Any) -> int:
    configured = getattr(shop, "platform_fee_bps", None)
    if configured is None:
        configured = os.environ.get("STRIPE_PLATFORM_FEE_BPS", "0")
    try:
        bps = int(configured)
    except (TypeError, ValueError):
        bps = 0
    return max(0, min(10000, bps))


def calculate_application_fee_amount(amount: float, platform_fee_bps: int) -> int:
    """Return fee amount in cents from dollar amount and basis points."""
    if amount <= 0 or platform_fee_bps <= 0:
        return 0
    cents = int(round(amount * 100))
    return max(0, int(round(cents * platform_fee_bps / 10000)))


def build_connect_context(shop: Any, amount: float) -> Dict[str, Any]:
    """Resolve Stripe Connect routing for a shop and payment amount."""
    platform_fee_bps = get_platform_fee_bps(shop)
    connect_account_id = getattr(shop, "stripe_connect_account_id", None)

    connect_ready = all(
        [
            is_stripe_connect_enabled(),
            bool(connect_account_id),
            bool(getattr(shop, "stripe_charges_enabled", False)),
            bool(getattr(shop, "stripe_payouts_enabled", False)),
        ]
    )

    application_fee_amount = calculate_application_fee_amount(amount, platform_fee_bps)
    return {
        "use_connect": connect_ready,
        "connect_account_id": connect_account_id if connect_ready else None,
        "platform_fee_bps": platform_fee_bps,
        "application_fee_amount": application_fee_amount if connect_ready else None,
    }
