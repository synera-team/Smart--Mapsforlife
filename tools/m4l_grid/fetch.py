"""Download the OpenStreetMap inputs for the Hanoi Fog-of-War grid (cached in .cache/).

    python tools/m4l_grid/fetch.py            # boundary, wards/communes, water, restricted areas, roads
"""
import sys

import overpass

CITY_RELATION = 1903516          # "Thành phố Hà Nội", admin_level=4
CITY_AREA = 3600000000 + CITY_RELATION
BBOX = (20.53, 105.27, 21.40, 106.03)   # S, W, N, E — covers the city relation with margin
TILE = 0.1
ROAD_TYPES = ("trunk|primary|secondary|tertiary|unclassified|residential|living_street|service|pedestrian|track|"
              "footway|path|cycleway|steps|road|trunk_link|primary_link|secondary_link|tertiary_link|bridleway|corridor")


def city():
    return overpass.query(f"[out:json][timeout:180];relation({CITY_RELATION});out geom;", label="city")


def units():
    return overpass.query(f"[out:json][timeout:600];area({CITY_AREA})->.hn;"
                          'relation(area.hn)["boundary"="administrative"]["admin_level"="6"];out geom;', label="units")


def water():
    return overpass.query(f"[out:json][timeout:600];area({CITY_AREA})->.hn;"
                          '(way["natural"="water"](area.hn);relation["natural"="water"](area.hn);'
                          'way["waterway"="riverbank"](area.hn);relation["waterway"="riverbank"](area.hn););out geom;', label="water")


def restricted():
    return overpass.query(f"[out:json][timeout:300];area({CITY_AREA})->.hn;"
                          '(way["landuse"="military"](area.hn);relation["landuse"="military"](area.hn););out geom;', label="military")


def road_tiles():
    s, w, n, e = BBOX
    rows, cols = round((n - s) / TILE), round((e - w) / TILE)
    for i in range(rows):
        for j in range(cols):
            box = (round(s + i * TILE, 4), round(w + j * TILE, 4), round(s + (i + 1) * TILE, 4), round(w + (j + 1) * TILE, 4))
            yield box, (lambda b=box, **kw: overpass.query(
                f"[out:json][timeout:300][bbox:{b[0]},{b[1]},{b[2]},{b[3]}];"
                f'way["highway"~"^({ROAD_TYPES})$"]["access"!~"^(private|no)$"];out geom qt;', label=f"roads {b}", **kw))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for name, fn in (("city", city), ("units", units), ("water", water), ("restricted", restricted)):
        data = fn()
        print(f"  {name}: {len(data['elements'])} phần tử · OSM {data['osm3s']['timestamp_osm_base']}", flush=True)
    if "--roads" in sys.argv:
        tiles = list(road_tiles())[::-1] if "--reverse" in sys.argv else list(road_tiles())
        for k, (box, fetch) in enumerate(tiles, 1):
            print(f"  roads {k}/{len(tiles)} {box}: {len(fetch()['elements'])} đường", flush=True)
