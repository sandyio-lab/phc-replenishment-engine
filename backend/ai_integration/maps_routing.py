"""
Google Maps Routing Module
===========================
Real road distance + ETA for inter-PHC stock transfers.

Provider chain (first one that answers wins, per donor):
  1. Google Maps Routes API  - only if GOOGLE_MAPS_API_KEY is set (needs GCP billing)
  2. OSRM (OpenStreetMap)    - free, no key, no card; public demo server by default
  3. Haversine estimate      - offline fallback, never fails

Flow:
  1. Pre-filter donor PHCs by straight-line (haversine) distance -> cheap, no API call
  2. Send only the closest candidates to Google Maps in ONE matrix request
  3. Return donors ranked by real drive time

Demo-safe: if GOOGLE_MAPS_API_KEY is missing, the request fails, or a route
element comes back without a result, that donor falls back to
haversine * road factor with an average rural speed. Every result is tagged
source = "google_maps" | "haversine_fallback".

Single responsibility: coordinates in, ranked estimates out. No database access.

Env vars (all optional):
  GOOGLE_MAPS_API_KEY  - enables tier 1 (Routes API must be enabled on the GCP project)
  OSRM_BASE_URL        - defaults to https://router.project-osrm.org (public demo server,
                         fine for a hackathon; self-host OSRM for real deployments)
  DISABLE_OSRM=true    - skip tier 2
"""

import os
import math
import time
import logging
from typing import List, Dict, Any, Optional

import requests
from pydantic import BaseModel

logger = logging.getLogger(__name__)

OSRM_BASE_URL = os.environ.get("OSRM_BASE_URL", "https://router.project-osrm.org").rstrip("/")
ROUTES_MATRIX_URL = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
FIELD_MASK = "originIndex,destinationIndex,duration,distanceMeters,status,condition"

DEFAULT_RADIUS_KM = 20.0      # matches the 20 km redistribution radius in the proposal
MAX_CANDIDATES = 10           # cap matrix size to protect quota
ROAD_FACTOR = 1.3             # road distance ~ 1.3x straight line (rural India)
FALLBACK_SPEED_KMPH = 30.0    # average rural transport speed for fallback ETA
REQUEST_TIMEOUT_S = 8
MAX_RETRIES = 2

# Simple in-memory cache: (rounded coords) -> (distance_km, duration_min, source)
_route_cache: Dict[tuple, tuple] = {}


class RouteEstimate(BaseModel):
    donor_id: Any
    distance_km: float
    duration_min: float
    source: str  # "google_maps" | "osrm" | "haversine_fallback"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _fallback_estimate(donor: Dict[str, Any], recipient: Dict[str, Any]) -> RouteEstimate:
    straight = haversine_km(donor["lat"], donor["lon"], recipient["lat"], recipient["lon"])
    road_km = straight * ROAD_FACTOR
    return RouteEstimate(
        donor_id=donor["id"],
        distance_km=round(road_km, 1),
        duration_min=round(road_km / FALLBACK_SPEED_KMPH * 60, 0),
        source="haversine_fallback",
    )


def _cache_key(donor: Dict[str, Any], recipient: Dict[str, Any]) -> tuple:
    return (
        round(donor["lat"], 4), round(donor["lon"], 4),
        round(recipient["lat"], 4), round(recipient["lon"], 4),
    )


def _latlng_waypoint(point: Dict[str, Any]) -> Dict[str, Any]:
    return {"waypoint": {"location": {"latLng": {"latitude": point["lat"], "longitude": point["lon"]}}}}


def _call_routes_matrix(donors: List[Dict[str, Any]], recipient: Dict[str, Any], api_key: str) -> Optional[list]:
    body = {
        "origins": [_latlng_waypoint(d) for d in donors],
        "destinations": [_latlng_waypoint(recipient)],
        "travelMode": "DRIVE",
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.post(ROUTES_MATRIX_URL, json=body, headers=headers, timeout=REQUEST_TIMEOUT_S)
            if resp.status_code == 200:
                return resp.json()
            last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            if resp.status_code in (400, 401, 403):  # config problem, retrying won't help
                break
        except requests.RequestException as e:
            last_error = str(e)
        if attempt < MAX_RETRIES:
            time.sleep(2 ** attempt)
    logger.warning("Routes API failed (%s) - using haversine fallback.", last_error)
    return None


def _call_osrm(donors: List[Dict[str, Any]], recipient: Dict[str, Any]) -> Optional[dict]:
    """One OSRM table request: many donors -> the recipient. Coordinates are lon,lat."""
    points = donors + [recipient]
    coords = ";".join(f"{p['lon']},{p['lat']}" for p in points)
    params = {
        "sources": ";".join(str(i) for i in range(len(donors))),
        "destinations": str(len(donors)),
        "annotations": "duration,distance",
    }
    url = f"{OSRM_BASE_URL}/table/v1/driving/{coords}"
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_S)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == "Ok":
                    return data
                last_error = f"OSRM code {data.get('code')}"
                break
            last_error = f"HTTP {resp.status_code}"
        except (requests.RequestException, ValueError) as e:
            last_error = str(e)
        if attempt < MAX_RETRIES:
            time.sleep(2 ** attempt)
    logger.warning("OSRM failed (%s) - using haversine fallback.", last_error)
    return None


def _parse_duration_s(value: Any) -> Optional[float]:
    """Routes API returns durations like '1234s'."""
    if value is None:
        return None
    try:
        return float(str(value).rstrip("s"))
    except ValueError:
        return None


def rank_donors(
    recipient: Dict[str, Any],
    donors: List[Dict[str, Any]],
    radius_km: float = DEFAULT_RADIUS_KM,
    max_candidates: int = MAX_CANDIDATES,
) -> List[RouteEstimate]:
    """
    recipient: {"id", "lat", "lon"}
    donors:    [{"id", "lat", "lon"}, ...]
    Returns donors within radius_km (straight-line pre-filter), ranked by drive time.
    """
    # 1. cheap pre-filter, closest first, capped
    scored = []
    for d in donors:
        if d["id"] == recipient["id"]:
            continue
        straight = haversine_km(d["lat"], d["lon"], recipient["lat"], recipient["lon"])
        if straight <= radius_km:
            scored.append((straight, d))
    scored.sort(key=lambda x: x[0])
    candidates = [d for _, d in scored[:max_candidates]]
    if not candidates:
        return []

    results: Dict[Any, RouteEstimate] = {}

    def _store(donor, km, mins, source):
        _route_cache[_cache_key(donor, recipient)] = (km, mins, source)
        results[donor["id"]] = RouteEstimate(
            donor_id=donor["id"], distance_km=km, duration_min=mins, source=source
        )

    # 2. serve from cache where possible
    to_fetch = []
    for d in candidates:
        cached = _route_cache.get(_cache_key(d, recipient))
        if cached:
            results[d["id"]] = RouteEstimate(
                donor_id=d["id"], distance_km=cached[0], duration_min=cached[1], source=cached[2]
            )
        else:
            to_fetch.append(d)

    # 3. tier 1: Google Maps (only if a key is configured)
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if to_fetch and api_key:
        matrix = _call_routes_matrix(to_fetch, recipient, api_key)
        for el in matrix or []:
            idx = el.get("originIndex")
            duration_s = _parse_duration_s(el.get("duration"))
            meters = el.get("distanceMeters")
            if idx is None or duration_s is None or meters is None:
                continue
            _store(to_fetch[idx], round(meters / 1000.0, 1), round(duration_s / 60.0, 0), "google_maps")
        to_fetch = [d for d in to_fetch if d["id"] not in results]

    # 4. tier 2: OSRM / OpenStreetMap (free, no key)
    if to_fetch and os.environ.get("DISABLE_OSRM", "").lower() != "true":
        data = _call_osrm(to_fetch, recipient)
        if data:
            durations, distances = data.get("durations") or [], data.get("distances") or []
            for i, donor in enumerate(to_fetch):
                try:
                    secs, meters = durations[i][0], distances[i][0]
                except (IndexError, TypeError):
                    continue
                if secs is None or meters is None:
                    continue
                _store(donor, round(meters / 1000.0, 1), round(secs / 60.0, 0), "osrm")
            to_fetch = [d for d in to_fetch if d["id"] not in results]

    # 5. tier 3: haversine estimate for anything still unresolved
    for d in to_fetch:
        results[d["id"]] = _fallback_estimate(d, recipient)

    return sorted(results.values(), key=lambda r: r.duration_min)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    recipient = {"id": "PHC-A", "lat": 12.7100, "lon": 77.6960}
    donors = [
        {"id": "PHC-B", "lat": 12.7400, "lon": 77.7200},
        {"id": "PHC-C", "lat": 12.6500, "lon": 77.6500},
        {"id": "PHC-D", "lat": 13.5000, "lon": 77.0000},  # far - filtered out
    ]
    for r in rank_donors(recipient, donors):
        print(r.model_dump_json())