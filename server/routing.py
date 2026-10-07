"""Định tuyến: proxy tới OSRM (hoặc máy chủ tương thích), sinh hướng dẫn tiếng Việt/Anh.
Có bộ nhớ đệm và phương án dự phòng đường chim bay khi máy chủ định tuyến không phản hồi."""
import json
import time
import urllib.parse
import urllib.request
from collections import OrderedDict

from geoutil import haversine_m

_cache = OrderedDict()
CACHE_MAX = 500
SPEED = {"foot": 4.8, "bike": 14.0, "driving": 22.0}  # km/h dùng cho ước lượng dự phòng

MOD_VI = {"left": "rẽ trái", "right": "rẽ phải", "slight left": "chếch trái", "slight right": "chếch phải",
          "sharp left": "rẽ gắt trái", "sharp right": "rẽ gắt phải", "straight": "đi thẳng", "uturn": "quay đầu"}
MOD_EN = {"left": "turn left", "right": "turn right", "slight left": "bear left", "slight right": "bear right",
          "sharp left": "sharp left", "sharp right": "sharp right", "straight": "continue straight", "uturn": "make a U-turn"}
DIR_VI = ["Bắc", "Đông Bắc", "Đông", "Đông Nam", "Nam", "Tây Nam", "Tây", "Tây Bắc"]
DIR_EN = ["north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"]


def _instr(step, lang="vi"):
    m = step.get("maneuver", {})
    t = m.get("type", "")
    mod = m.get("modifier", "")
    name = step.get("name") or ""
    vi = lang == "vi"
    on = (f" vào {name}" if vi else f" onto {name}") if name else ""
    if t == "depart":
        b = m.get("bearing_after", 0)
        d = (DIR_VI if vi else DIR_EN)[int(((b + 22.5) % 360) // 45)]
        return (f"Bắt đầu đi về hướng {d}" + (f" trên {name}" if name else "")) if vi else (f"Head {d}" + (f" on {name}" if name else ""))
    if t == "arrive":
        return "Đến nơi" if vi else "Arrive at destination"
    if t in ("roundabout", "rotary"):
        ex_ = m.get("exit")
        return (f"Vào vòng xuyến, ra ở lối thứ {ex_}{on}" if vi else f"At the roundabout take exit {ex_}{on}") if ex_ else ("Đi qua vòng xuyến" if vi else "Go through the roundabout")
    act = (MOD_VI if vi else MOD_EN).get(mod, "tiếp tục" if vi else "continue")
    if t in ("continue", "new name"):
        return (f"Tiếp tục{(' trên ' + name) if name else ''}" if vi else f"Continue{(' on ' + name) if name else ''}")
    if t == "merge":
        return ("Nhập làn" if vi else "Merge") + on
    if t in ("on ramp", "off ramp"):
        return ("Đi vào đường nhánh" if vi else "Take the ramp") + on
    if t == "fork":
        return (f"Tại ngã ba, {act}" if vi else f"At the fork, {act}") + on
    if t == "end of road":
        return (f"Cuối đường, {act}" if vi else f"At the end of the road, {act}") + on
    return act[:1].upper() + act[1:] + on


def route(settings, mode, frm, to, lang="vi"):
    """frm/to: (lng, lat). mode: foot|bike|driving"""
    mode = mode if mode in ("foot", "bike", "driving") else "foot"
    key = (mode, round(frm[0], 5), round(frm[1], 5), round(to[0], 5), round(to[1], 5), lang)
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    cfg = settings.get("routing") or {}
    base = (cfg.get(mode) or "").rstrip("/")
    res = None
    err = None
    if base:
        coords = f"{frm[0]:.6f},{frm[1]:.6f};{to[0]:.6f},{to[1]:.6f}"
        prof = "driving"  # máy chủ FOSSGIS dùng đường dẫn profile trong base URL
        url = f"{base}/route/v1/{prof}/{coords}?overview=full&geometries=geojson&steps=true&alternatives=false"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Xanh24-Maps/1.0"})
            with urllib.request.urlopen(req, timeout=float(cfg.get("timeout", 8))) as r:
                data = json.loads(r.read().decode())
            if data.get("code") == "Ok" and data.get("routes"):
                rt = data["routes"][0]
                steps = []
                for leg in rt.get("legs", []):
                    for s in leg.get("steps", []):
                        steps.append({"text": _instr(s, lang), "distance": round(s.get("distance", 0)),
                                      "duration": round(s.get("duration", 0)),
                                      "location": s.get("maneuver", {}).get("location"),
                                      "type": s.get("maneuver", {}).get("type"),
                                      "modifier": s.get("maneuver", {}).get("modifier", "")})
                dist = rt["distance"]
                dur = rt["duration"]
                if mode == "foot":
                    dur = max(dur, dist / (SPEED["foot"] / 3.6))
                res = {"ok": True, "mode": mode, "distance": round(dist), "duration": round(dur),
                       "geometry": rt["geometry"], "steps": steps, "source": "osrm"}
            else:
                err = data.get("message") or data.get("code")
        except Exception as e:  # noqa
            err = str(e)
    if res is None:
        d = haversine_m(frm[1], frm[0], to[1], to[0]) * 1.3
        res = {"ok": True, "mode": mode, "distance": round(d), "duration": round(d / (SPEED[mode] / 3.6)),
               "geometry": {"type": "LineString", "coordinates": [list(frm), list(to)]},
               "steps": [{"text": "Không kết nối được máy chủ định tuyến — hiển thị hướng ước lượng" if lang == "vi" else
                          "Routing server unavailable — showing estimated direction", "distance": round(d)}],
               "source": "estimate", "error": err}
    if res.get("source") == "osrm":
        _cache[key] = res
    if len(_cache) > CACHE_MAX:
        _cache.popitem(last=False)
    return res
