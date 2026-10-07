"""Tra địa chỉ theo toạ độ (reverse geocoding) cho tính năng chọn điểm bất kỳ trên bản đồ.
Mặc định dùng Nominatim (OpenStreetMap) — có bộ nhớ đệm và giới hạn 1 yêu cầu/giây theo chính sách sử dụng.
Có thể thay bằng máy chủ Nominatim riêng / dịch vụ tương thích tại Cấu hình → geocode.reverse_url."""
import json
import threading
import time
import urllib.parse
import urllib.request
from collections import OrderedDict

_cache = OrderedDict()
_lock = threading.Lock()
_last = [0.0]
CACHE_MAX = 3000
DEFAULT_URL = "https://nominatim.openstreetmap.org/reverse"


def _addr_text(a, display):
    parts = []
    hn, road = a.get("house_number"), a.get("road") or a.get("pedestrian") or a.get("footway") or a.get("path")
    if road:
        parts.append(f"{hn} {road}" if hn else road)
    for k in ("neighbourhood", "quarter", "suburb", "city_district"):
        if a.get(k) and a[k] not in parts:
            parts.append(a[k])
            break
    city = a.get("city") or a.get("town") or a.get("state")
    if city:
        parts.append(city)
    return ", ".join(parts) or (display or "")


def reverse(settings, lat, lng, lang="vi"):
    cfg = (settings.get("geocode") or {})
    if cfg.get("enabled") is False:
        return None
    key = (round(lat, 4), round(lng, 4), lang)
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    url = cfg.get("reverse_url") or DEFAULT_URL
    q = urllib.parse.urlencode({"format": "jsonv2", "lat": f"{lat:.6f}", "lon": f"{lng:.6f}", "zoom": 18,
                                "addressdetails": 1, "accept-language": "vi,en" if lang == "vi" else "en,vi"})
    with _lock:  # tối đa 1 yêu cầu/giây tới máy chủ công cộng
        wait = 1.05 - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
    try:
        req = urllib.request.Request(f"{url}?{q}", headers={"User-Agent": cfg.get("user_agent") or "Xanh24-MapsForLife/1.1 (+https://www.xanh24.com)"})
        with urllib.request.urlopen(req, timeout=float(cfg.get("timeout", 6))) as r:
            d = json.loads(r.read().decode("utf-8"))
    except Exception:
        return None
    if not isinstance(d, dict) or d.get("error"):
        res = {"name": "", "address": "", "road": ""}
    else:
        a = d.get("address") or {}
        name = d.get("name") or a.get("amenity") or a.get("shop") or a.get("building") or a.get("tourism") or ""
        res = {"name": name, "address": _addr_text(a, d.get("display_name")), "road": a.get("road") or "",
               "category": d.get("category") or "", "type": d.get("type") or "", "osm": f"{d.get('osm_type', '')}/{d.get('osm_id', '')}"}
    with _lock:
        _cache[key] = res
        while len(_cache) > CACHE_MAX:
            _cache.popitem(last=False)
    return res


# ---------------------------------------------------------------- tìm địa chỉ / địa điểm bất kỳ (forward geocoding)
_scache = OrderedDict()
HANOI_BBOX = (105.25, 20.55, 106.05, 21.40)  # lng_min, lat_min, lng_max, lat_max


def _get_json(url, headers=None, data=None, timeout=6):
    h = {"User-Agent": "Xanh24-MapsForLife/1.3 (+https://www.xanh24.com)", "Accept": "application/json"}
    h.update(headers or {})
    body = json.dumps(data).encode() if data is not None else None
    if body is not None:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _photon(q, lat, lng, limit, cfg):
    base = cfg.get("search_url") or "https://photon.komoot.io/api/"
    b = HANOI_BBOX
    qs = urllib.parse.urlencode({"q": q, "limit": limit, "lat": f"{lat:.5f}", "lon": f"{lng:.5f}",
                                 "bbox": f"{b[0]},{b[1]},{b[2]},{b[3]}"})
    d = _get_json(f"{base}?{qs}")
    out = []
    for f in d.get("features", []):
        p, c = f.get("properties", {}), f.get("geometry", {}).get("coordinates", [None, None])
        if c[0] is None:
            continue
        name = p.get("name") or " ".join(x for x in (p.get("housenumber"), p.get("street")) if x)
        addr = ", ".join(x for x in (
            " ".join(x for x in (p.get("housenumber"), p.get("street")) if x) if p.get("name") else "",
            p.get("locality") or p.get("district"), p.get("city") or p.get("county")) if x)
        kind = p.get("osm_value") or p.get("type") or ""
        out.append({"name": name or addr, "address": addr, "lat": c[1], "lng": c[0], "kind": kind, "src": "photon"})
    return out


def _nominatim_search(q, limit, cfg, lang):
    base = cfg.get("nominatim_search_url") or "https://nominatim.openstreetmap.org/search"
    b = HANOI_BBOX
    qs = urllib.parse.urlencode({"q": q, "format": "jsonv2", "limit": limit, "countrycodes": "vn", "addressdetails": 1,
                                 "viewbox": f"{b[0]},{b[3]},{b[2]},{b[1]}", "bounded": 1,
                                 "accept-language": "vi,en" if lang == "vi" else "en,vi"})
    with _lock:
        wait = 1.05 - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
    d = _get_json(f"{base}?{qs}")
    out = []
    for r in d if isinstance(d, list) else []:
        a = r.get("address") or {}
        out.append({"name": r.get("name") or (r.get("display_name") or "").split(",")[0], "address": _addr_text(a, r.get("display_name")),
                    "lat": float(r["lat"]), "lng": float(r["lon"]), "kind": r.get("type") or "", "src": "nominatim"})
    return out


def search(settings, q, lat=21.0278, lng=105.8342, lang="vi", limit=8):
    cfg = settings.get("geocode") or {}
    if cfg.get("enabled") is False or len(q.strip()) < 2:
        return []
    key = (q.strip().lower(), round(lat, 2), round(lng, 2), lang)
    with _lock:
        if key in _scache:
            _scache.move_to_end(key)
            return _scache[key]
    res = []
    try:
        res = _photon(q, lat, lng, limit, cfg)
    except Exception:
        res = []
    if not res:
        try:
            res = _nominatim_search(q, limit, cfg, lang)
        except Exception:
            res = []
    with _lock:
        _scache[key] = res
        while len(_scache) > 2000:
            _scache.popitem(last=False)
    return res


# ---------------------------------------------------------------- định vị theo Wi-Fi / trạm di động (cho kiosk không có GPS)
def wifi_locate(settings, wifi, cells=None):
    """wifi: [{"mac": "aa:bb:..", "rssi": -60}], trả {lat, lng, acc, src} hoặc None.
    Ưu tiên Google Geolocation API (cùng dữ liệu với Google Maps) khi có khoá; dự phòng BeaconDB (miễn phí, mã nguồn mở)."""
    import os
    cfg = settings.get("geocode") or {}
    aps = [{"macAddress": w["mac"], "signalStrength": int(w.get("rssi") or -80)} for w in (wifi or []) if w.get("mac")]
    aps = sorted(aps, key=lambda a: -a["signalStrength"])[:30]
    key = os.environ.get("GOOGLE_GEOLOCATION_API_KEY") or cfg.get("google_geolocation_key")
    body = {"considerIp": False, "wifiAccessPoints": aps}
    if cells:
        body["cellTowers"] = cells[:10]
    if key and len(aps) >= 2:
        try:
            d = _get_json(f"https://www.googleapis.com/geolocation/v1/geolocate?key={urllib.parse.quote(key)}", data=body, timeout=8)
            if "location" in d:
                return {"lat": d["location"]["lat"], "lng": d["location"]["lng"], "acc": d.get("accuracy", 100), "src": "wifi-google"}
        except Exception:
            pass
    if len(aps) >= 2:
        try:
            d = _get_json(cfg.get("beacondb_url") or "https://api.beacondb.net/v1/geolocate", data=body, timeout=8)
            if "location" in d:
                return {"lat": d["location"]["lat"], "lng": d["location"]["lng"], "acc": d.get("accuracy", 200), "src": "wifi-beacondb"}
        except Exception:
            pass
    return None
