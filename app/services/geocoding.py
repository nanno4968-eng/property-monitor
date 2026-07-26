"""Optional geocoding via OpenStreetMap Nominatim - free, but rate-limited to
~1 request/second and requires a descriptive user agent per OSM's usage
policy. Disabled by default (GEOCODING_ENABLED=false); the pipeline works
fine without coordinates, it just skips the location-score component and
flags geocode confidence as low."""
from __future__ import annotations

from dataclasses import dataclass

from app.config import settings

_geolocator = None
_geocode_fn = None


def _get_geocode_fn():
    global _geolocator, _geocode_fn
    if _geocode_fn is None:
        from geopy.extra.rate_limiter import RateLimiter
        from geopy.geocoders import Nominatim

        _geolocator = Nominatim(user_agent=settings.geocoding_user_agent)
        _geocode_fn = RateLimiter(_geolocator.geocode, min_delay_seconds=1.1, max_retries=1)
    return _geocode_fn


@dataclass
class GeocodeResult:
    latitude: float | None
    longitude: float | None
    confidence: str  # high, medium, low, none


def geocode_address(address: str | None) -> GeocodeResult:
    if not settings.geocoding_enabled or not address:
        return GeocodeResult(None, None, "none")
    try:
        geocode = _get_geocode_fn()
        location = geocode(f"{address}, South Africa")
        if location:
            return GeocodeResult(location.latitude, location.longitude, "medium")
    except Exception:
        pass
    return GeocodeResult(None, None, "low")
