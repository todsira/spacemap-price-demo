"""Generate the 10 x 10 km square layers and their attributes.

Outputs:
  web/data/layer1_ports.geojson ... layer4_border.geojson  (plain GeoJSON, opens in QGIS)
  web/data/layers.js                                         (same data + summaries, for the web app)
"""
import json
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import requests
from pyproj import Geod, Transformer
from shapely import STRtree
from shapely.geometry import LineString, Point, Polygon, box, shape
from shapely import transform as shp_transform
from shapely.ops import linemerge, substring, unary_union

sys.path.insert(0, str(Path(__file__).parent))
import config as C  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "build" / "sources"
OUT = ROOT / "web" / "data"
HALF = C.SQUARE_KM * 1000 / 2
GEOD = Geod(ellps="WGS84")

DIRS = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}
DIR_NAMES = {"N": "north", "E": "east", "S": "south", "W": "west"}


# --------------------------------------------------------------------------- projections
def utm_epsg(lon, lat):
    zone = int((lon + 180) // 6) + 1
    return (32600 if lat >= 0 else 32700) + zone


_transformers = {}


def to_utm(epsg):
    if ("fwd", epsg) not in _transformers:
        _transformers[("fwd", epsg)] = Transformer.from_crs(4326, epsg, always_xy=True)
    return _transformers[("fwd", epsg)]


def to_wgs(epsg):
    if ("inv", epsg) not in _transformers:
        _transformers[("inv", epsg)] = Transformer.from_crs(epsg, 4326, always_xy=True)
    return _transformers[("inv", epsg)]


# --------------------------------------------------------------------------- reference data
class RefData:
    """Land, coastline, country and marine-name data, projected per UTM zone on demand."""

    def __init__(self):
        bbox = box(*C.REGION_BBOX)
        print("loading OSM land polygons ...")
        land = gpd.read_file(
            SRC / "osm_land/simplified-land-polygons-complete-3857/simplified_land_polygons.shp",
            bbox=gpd.GeoSeries([bbox], crs=4326).to_crs(3857).iloc[0],
        ).to_crs(4326)
        self.land_wgs = list(land.geometry.intersection(bbox))
        countries = gpd.read_file(SRC / "ne_countries/ne_10m_admin_0_countries.shp", bbox=C.REGION_BBOX)
        self.countries_wgs = list(zip(countries["ADMIN"], countries.geometry))
        marine = gpd.read_file(SRC / "ne_marine/ne_10m_geography_marine_polys.shp", bbox=C.REGION_BBOX)
        # smaller (more specific) seas first
        marine = marine.assign(_a=marine.to_crs(3857).area).sort_values("_a")
        self.marine_wgs = list(zip(marine["name"], marine.geometry))
        self._zones = {}

    def zone(self, epsg):
        if epsg not in self._zones:
            t = to_utm(epsg)

            def f(g):
                return shp_transform(g, lambda xy: np.column_stack(t.transform(xy[:, 0], xy[:, 1])))

            land = [f(g) for g in self.land_wgs if not g.is_empty]
            coast = [g.boundary for g in land]
            # the mainland is the largest land polygon; everything else counts as an island
            parts = [q for g in land for q in getattr(g, "geoms", [g])]
            mainland = max(parts, key=lambda q: q.area)
            countries = [(n, f(g)) for n, g in self.countries_wgs]
            self._zones[epsg] = {
                "land": land,
                "land_tree": STRtree(land),
                "coast": coast,
                "coast_tree": STRtree(coast),
                "countries": countries,
                "mainland": mainland,
            }
        return self._zones[epsg]

    def land_fraction(self, sq_utm, epsg):
        z = self.zone(epsg)
        idx = z["land_tree"].query(sq_utm)
        if len(idx) == 0:
            return 0.0
        inter = unary_union([z["land"][i].intersection(sq_utm) for i in idx])
        return inter.area / sq_utm.area

    def mainland_near(self, x, y, epsg, radius_m):
        """The mainland clipped to a box around (x, y): much faster for repeated overlays."""
        return self.zone(epsg)["mainland"].intersection(
            box(x - radius_m, y - radius_m, x + radius_m, y + radius_m))

    def coast_distance_km(self, pt_utm, epsg):
        z = self.zone(epsg)
        i = z["coast_tree"].nearest(pt_utm)
        return z["coast"][i].distance(pt_utm) / 1000

    def country_shares(self, sq_utm, epsg):
        shares = {}
        for name, g in self.zone(epsg)["countries"]:
            if g.intersects(sq_utm):
                a = g.intersection(sq_utm).area / sq_utm.area
                if a > 0.001:
                    shares[name] = round(a * 100, 1)
        return dict(sorted(shares.items(), key=lambda kv: -kv[1]))

    def marine_name(self, lon, lat):
        p = Point(lon, lat)
        for name, g in self.marine_wgs:
            if g.contains(p):
                return name
        name, _ = min(self.marine_wgs, key=lambda ng: ng[1].distance(p))
        return name


# --------------------------------------------------------------------------- squares
def make_square(lon, lat, ref, layer, sid, extra=None):
    epsg = utm_epsg(lon, lat)
    e, n = to_utm(epsg).transform(lon, lat)
    # Build the square in a transverse Mercator centred on the square itself (scale = 1 at
    # the centre) so each side is 10.000 km on the ground, north-up.
    local = f"+proj=tmerc +lat_0={lat} +lon_0={lon} +k=1 +x_0=0 +y_0=0 +ellps=WGS84 +units=m"
    inv = Transformer.from_crs(local, 4326, always_xy=True).transform
    corners = [(-HALF, -HALF), (HALF, -HALF), (HALF, HALF), (-HALF, HALF)]
    pts = []
    for k in range(4):  # densify edges
        (x0, y0), (x1, y1) = corners[k], corners[(k + 1) % 4]
        for t in range(10):
            pts.append((x0 + (x1 - x0) * t / 10, y0 + (y1 - y0) * t / 10))
    ring = [inv(x, y) for x, y in pts]
    ring.append(ring[0])
    corners_wgs = {k: inv(*c) for k, c in zip(["SW", "SE", "NE", "NW"], corners)}
    fwd = to_utm(epsg).transform
    sq = Polygon([fwd(x, y) for x, y in ring])  # same square in UTM for land / country overlays
    land_frac = ref.land_fraction(sq, epsg)
    shares = ref.country_shares(sq, epsg)
    props = {
        "id": sid,
        "layer": layer,
        "center_lat": round(lat, 6),
        "center_lon": round(lon, 6),
        "corners": {k: [round(v[1], 6), round(v[0], 6)] for k, v in corners_wgs.items()},
        "size_km": f"{C.SQUARE_KM:g} x {C.SQUARE_KM:g}",
        "area_km2": round(C.SQUARE_KM ** 2, 2),
        "utm_zone": f"{epsg % 100}{'N' if epsg < 32700 else 'S'}",
        "utm_e": round(e),
        "utm_n": round(n),
        "land_pct": round(land_frac * 100, 1),
        "sea_pct": round((1 - land_frac) * 100, 1),
        "surface": "land" if land_frac > 0.5 else "sea",
        "country_share_pct": shares,
        "coast_dist_km": round(ref.coast_distance_km(Point(e, n), epsg), 2),
    }
    if land_frac < 0.999:
        props["sea_area"] = ref.marine_name(lon, lat)
    if extra:
        props.update(extra)
    geom = {"type": "Polygon", "coordinates": [[[round(x, 6), round(y, 6)] for x, y in ring]]}
    return {"type": "Feature", "geometry": geom, "properties": props}, sq, epsg


def offset_lonlat(lon, lat, dx_m, dy_m):
    epsg = utm_epsg(lon, lat)
    e, n = to_utm(epsg).transform(lon, lat)
    return to_wgs(epsg).transform(e + dx_m, n + dy_m)


def port_props(p):
    return {"group": p["id"], "port_th": p["name_th"], "port_en": p["name_en"]}


def layer_ports(ref):
    feats = []
    for p in C.PORTS:
        f, _, _ = make_square(p["lon"], p["lat"], ref, "ports", f"PORT-{p['id']}", port_props(p))
        feats.append(f)
    return feats


def sea_block_centers(p, direction, offsets_m=None):
    """Centres of the block cells. offsets_m[j] slides column j seaward (+) or landward (-)."""
    ox, oy = DIRS[direction]
    ax, ay = -oy, ox  # perpendicular
    step = C.SQUARE_KM * 1000
    out = []
    for i in range(C.SEA_BLOCK_OUT):
        for j in range(C.SEA_BLOCK_ACROSS):
            along = step * (i + 0.5) + (offsets_m[j] if offsets_m else 0)
            across = step * (j - (C.SEA_BLOCK_ACROSS - 1) / 2)
            dx, dy = ox * along + ax * across, oy * along + ay * across
            out.append((i, j, *offset_lonlat(p["lon"], p["lat"], dx, dy)))
    return out


def column_offset(p, j, mainland, epsg):
    """Smallest slide (closest to the coast) at which every cell of column j stays within
    SEA_MAX_MAINLAND_FRACTION mainland overlap. Islands are not part of `mainland`."""
    ox, oy = DIRS[p["seaward"]]
    ax, ay = -oy, ox
    step = C.SQUARE_KM * 1000
    e0, n0 = to_utm(epsg).transform(p["lon"], p["lat"])
    across = step * (j - (C.SEA_BLOCK_ACROSS - 1) / 2)

    def ok(t):
        for i in range(C.SEA_BLOCK_OUT):
            along = step * (i + 0.5) + t
            x, y = e0 + ox * along + ax * across, n0 + oy * along + ay * across
            sq = box(x - HALF, y - HALF, x + HALF, y + HALF)
            if mainland.intersection(sq).area / sq.area > C.SEA_MAX_MAINLAND_FRACTION:
                return False
        return True

    lo_m, hi_m = C.SEA_SLIDE_RANGE_KM[0] * 1000, C.SEA_SLIDE_RANGE_KM[1] * 1000
    t = lo_m
    if ok(t):
        return t
    while t < hi_m:
        t2 = t + 100
        if ok(t2):
            lo, hi = t, t2  # refine to < 10 m
            while hi - lo > 10:
                mid = (lo + hi) / 2
                lo, hi = (lo, mid) if ok(mid) else (mid, hi)
            return hi
        t = t2
    print(f"  WARNING {p['id']} column {j + 1}: no position within the slide range")
    return hi_m


def block_land_fraction(p, direction, ref):
    fr = []
    for _, _, lon, lat in sea_block_centers(p, direction):
        epsg = utm_epsg(lon, lat)
        e, n = to_utm(epsg).transform(lon, lat)
        fr.append(ref.land_fraction(box(e - HALF, n - HALF, e + HALF, n + HALF), epsg))
    return sum(fr) / len(fr)


def layer_sea_blocks(ref):
    feats = []
    for p in C.PORTS:
        lf = {d: block_land_fraction(p, d, ref) for d in DIRS}
        best = min(lf, key=lf.get)
        print(f"  {p['id']} land fraction per direction: "
              + ", ".join(f"{d}={v * 100:.0f}%" for d, v in lf.items()))
        if best != p["seaward"] and lf[best] + 0.02 < lf[p["seaward"]]:
            print(f"  WARNING {p['id']}: configured seaward={p['seaward']} but {best} has less land")
        epsg = utm_epsg(p["lon"], p["lat"])
        e0, n0 = to_utm(epsg).transform(p["lon"], p["lat"])
        mainland = ref.mainland_near(e0, n0, epsg, 90_000)
        offsets = [column_offset(p, j, mainland, epsg) for j in range(C.SEA_BLOCK_ACROSS)]
        print(f"  {p['id']} column slides (km): " + ", ".join(f"{t / 1000:+.2f}" for t in offsets))
        for i, j, lon, lat in sea_block_centers(p, p["seaward"], offsets):
            sid = f"SEA-{p['id']}-R{i + 1}C{j + 1}"
            dist = GEOD.inv(p["lon"], p["lat"], lon, lat)[2] / 1000
            extra = port_props(p) | {
                "seaward": DIR_NAMES[p["seaward"]],
                "block_row": f"{i + 1} of {C.SEA_BLOCK_OUT} (outward)",
                "block_col": f"{j + 1} of {C.SEA_BLOCK_ACROSS} (across)",
                "port_dist_km": round(dist, 2),
                "column_offset_km": round(offsets[j] / 1000, 2),
            }
            f, sq, _ = make_square(lon, lat, ref, "sea_blocks", sid, extra)
            pr = f["properties"]
            pr["mainland_pct"] = round(mainland.intersection(sq).area / sq.area * 100, 1)
            pr["island_pct"] = round(max(pr["land_pct"] - pr["mainland_pct"], 0), 1)
            feats.append(f)
    return feats


def layer_points(ref):
    feats = []
    for pt in C.POINTS:
        f, _, _ = make_square(pt["lon"], pt["lat"], ref, "points", f"PT-{pt['id']}",
                              {"group": pt["id"], "point_name": pt["name_en"]})
        feats.append(f)
    return feats


def load_border_utm():
    b = gpd.read_file(SRC / "ne_boundaries/ne_10m_admin_0_boundary_lines_land.shp")
    sel = b[b.ADM0_LEFT.isin(["Thailand", "Myanmar"]) & b.ADM0_RIGHT.isin(["Thailand", "Myanmar"])]
    merged = linemerge(unary_union(list(sel.geometry)))
    parts = [merged] if merged.geom_type == "LineString" else list(merged.geoms)
    # chain parts north -> south (start of each part from the northern end)
    parts = [LineString(list(g.coords)[::-1]) if g.coords[0][1] < g.coords[-1][1] else g for g in parts]
    parts.sort(key=lambda g: -g.coords[0][1])
    coords = []
    for g in parts:
        coords.extend(g.coords)
    lon0, lat0 = coords[0]
    epsg = utm_epsg(sum(c[0] for c in coords) / len(coords), lat0)
    f = to_utm(epsg).transform
    return LineString([f(x, y) for x, y in coords]), epsg, len(parts)


def maritime_extension_utm(land_line, epsg, ref):
    """Continue the land border along Natural Earth's maritime border line (down the Kra
    estuary and into the Andaman Sea) until it is BORDER_SEA_EXTENSION_KM from the mainland."""
    if C.BORDER_SEA_EXTENSION_KM <= 0:
        return None
    m = gpd.read_file(SRC / "ne_maritime/ne_10m_admin_0_boundary_lines_maritime_indicator.shp",
                      bbox=C.REGION_BBOX).to_crs(epsg)
    end = Point(land_line.coords[-1])
    lines = [q for g in m.geometry for q in getattr(g, "geoms", [g])]
    sea = min(lines, key=lambda q: q.distance(end))
    if sea.distance(end) > 2000:
        print("  WARNING no maritime border line starts at the end of the land border")
        return None
    if Point(sea.coords[0]).distance(end) > Point(sea.coords[-1]).distance(end):
        sea = LineString(list(sea.coords)[::-1])
    x, y = end.x, end.y
    mainland = ref.mainland_near(x, y, epsg, 250_000)
    target = C.BORDER_SEA_EXTENSION_KM * 1000
    d = 0.0
    while d < sea.length and mainland.distance(sea.interpolate(d)) < target:
        d += 100
    lo, hi = max(d - 100, 0), min(d, sea.length)  # refine to < 5 m
    while hi - lo > 5:
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if mainland.distance(sea.interpolate(mid)) >= target else (mid, hi)
    return substring(sea, 0, hi)


def border_centers(line):
    step = C.SQUARE_KM * 1000
    L = line.length
    if C.BORDER_STEP_MODE == "along":
        return [d for d in frange(0, L, step)]
    centers = [0.0]
    cur = line.interpolate(0)
    d, ds = 0.0, 50.0
    while d < L:
        d2 = min(d + ds, L)
        p = line.interpolate(d2)
        if max(abs(p.x - cur.x), abs(p.y - cur.y)) >= step:
            lo, hi = d, d2  # refine crossing point to < 1 m
            while hi - lo > 1:
                mid = (lo + hi) / 2
                q = line.interpolate(mid)
                if max(abs(q.x - cur.x), abs(q.y - cur.y)) >= step:
                    hi = mid
                else:
                    lo = mid
            centers.append(hi)
            cur = line.interpolate(hi)
            d = hi
        else:
            d = d2
    end = line.interpolate(L)
    if max(abs(end.x - cur.x), abs(end.y - cur.y)) > HALF:
        centers.append(L)
    return centers


def frange(a, b, s):
    x = a
    while x <= b:
        yield x
        x += s


def layer_border(ref):
    land_line, epsg, nparts = load_border_utm()
    sea_line = maritime_extension_utm(land_line, epsg, ref)
    land_km = land_line.length / 1000
    sea_km = sea_line.length / 1000 if sea_line else 0.0
    line = LineString(list(land_line.coords) + list(sea_line.coords)[1:]) if sea_line else land_line
    print(f"  border: {land_km:.1f} km land ({nparts} part(s)) + {sea_km:.1f} km maritime, UTM EPSG:{epsg}")
    inv = to_wgs(epsg).transform
    feats = []
    for k, d in enumerate(border_centers(line), start=1):
        pt = line.interpolate(d)
        lon, lat = inv(pt.x, pt.y)
        section = "land" if d <= land_line.length + 1 else "maritime"
        f, _, _ = make_square(lon, lat, ref, "border", f"BORDER-{k:03d}",
                              {"group": "TH-MM", "along_border_km": round(d / 1000, 1),
                               "border_section": section})
        feats.append(f)

    def wgs(g):
        return [[round(x, 5), round(y, 5)] for x, y in (inv(*c) for c in g.coords)] if g else []
    return feats, land_km, sea_km, wgs(land_line), wgs(sea_line)


# --------------------------------------------------------------------------- enrichment (cached)
def load_cache(name):
    p = SRC / name
    return json.loads(p.read_text()) if p.exists() else {}


def save_cache(name, data):
    (SRC / name).write_text(json.dumps(data, ensure_ascii=False, indent=0))


def enrich_geocode(features):
    cache = load_cache("geocode_cache.json")
    sess = requests.Session()
    sess.headers["User-Agent"] = C.USER_AGENT
    todo = [(f, lang) for f in features for lang in ("en", "th")
            if f"{f['properties']['center_lat']},{f['properties']['center_lon']},{lang}" not in cache]
    for n, (f, lang) in enumerate(todo, 1):
        pr = f["properties"]
        key = f"{pr['center_lat']},{pr['center_lon']},{lang}"
        try:
            r = sess.get(C.NOMINATIM_URL, params={
                "lat": pr["center_lat"], "lon": pr["center_lon"], "format": "jsonv2",
                "zoom": 14, "accept-language": lang}, timeout=30)
            cache[key] = r.json() if r.ok else {"error": r.status_code}
        except requests.RequestException as e:
            print("    geocode failed", key, e)
        if n % 20 == 0 or n == len(todo):
            print(f"    geocode {n}/{len(todo)}")
            save_cache("geocode_cache.json", cache)
        time.sleep(1.1)  # Nominatim usage policy: max 1 request / second
    save_cache("geocode_cache.json", cache)

    for f in features:
        pr = f["properties"]
        for lang in ("en", "th"):
            res = cache.get(f"{pr['center_lat']},{pr['center_lon']},{lang}", {})
            a = res.get("address") or {}
            if not a:
                continue
            sfx = "" if lang == "en" else "_th"
            pr["country" + sfx] = a.get("country")
            pr["province" + sfx] = a.get("state") or a.get("province") or a.get("region")
            pr["district" + sfx] = a.get("county") or a.get("city_district") or a.get("district")
            pr["subdistrict" + sfx] = (a.get("suburb") or a.get("town") or a.get("village")
                                       or a.get("municipality") or a.get("hamlet"))
        if not pr.get("country") and pr["country_share_pct"]:
            pr["country"] = next(iter(pr["country_share_pct"]))


def enrich_elevation(features):
    cache = load_cache("elevation_cache.json")
    sess = requests.Session()
    sess.headers["User-Agent"] = C.USER_AGENT
    for dataset, want_land in (("srtm90m", True), ("gebco2020", False)):
        pts = [f["properties"] for f in features if (f["properties"]["surface"] == "land") == want_land]
        todo = [p for p in pts if f"{dataset}:{p['center_lat']},{p['center_lon']}" not in cache]
        for k in range(0, len(todo), 100):
            chunk = todo[k:k + 100]
            locs = "|".join(f"{p['center_lat']},{p['center_lon']}" for p in chunk)
            try:
                r = sess.get(f"{C.OPENTOPODATA_URL}/{dataset}", params={"locations": locs}, timeout=60)
                r.raise_for_status()
                for p, res in zip(chunk, r.json()["results"]):
                    cache[f"{dataset}:{p['center_lat']},{p['center_lon']}"] = res["elevation"]
            except (requests.RequestException, KeyError, ValueError) as e:
                print(f"    elevation {dataset} failed: {e}")
            save_cache("elevation_cache.json", cache)
            time.sleep(1.1)
        for p in pts:
            v = cache.get(f"{dataset}:{p['center_lat']},{p['center_lon']}")
            if v is None:
                continue
            if want_land:
                p["elevation_m"] = round(v)
            else:
                p["depth_m"] = round(-v) if v < 0 else 0


# --------------------------------------------------------------------------- summaries
def extent_km(features):
    lons = [c[0] for f in features for c in f["geometry"]["coordinates"][0]]
    lats = [c[1] for f in features for c in f["geometry"]["coordinates"][0]]
    lo0, lo1, la0, la1 = min(lons), max(lons), min(lats), max(lats)
    mid = (la0 + la1) / 2
    width = GEOD.inv(lo0, mid, lo1, mid)[2] / 1000
    height = GEOD.inv((lo0 + lo1) / 2, la0, (lo0 + lo1) / 2, la1)[2] / 1000
    return round(width, 1), round(height, 1), [la0, lo0, la1, lo1]


def union_area_km2(features):
    geoms = [shape(f["geometry"]) for f in features]
    u = unary_union(geoms)
    return round(abs(GEOD.geometry_area_perimeter(u)[0]) / 1e6, 1)


def summarize(features, groups=None, **extra):
    w, h, bounds = extent_km(features)
    s = {
        "count": len(features),
        "square_size_km": f"{C.SQUARE_KM:g} x {C.SQUARE_KM:g}",
        "total_area_km2": round(len(features) * C.SQUARE_KM ** 2, 1),
        "covered_area_km2": union_area_km2(features),
        "extent_km": {"width_ew": w, "height_ns": h},
        "bounds": bounds,
    }
    if groups:
        s["groups"] = []
        for gid, label in groups:
            gf = [f for f in features if f["properties"].get("group") == gid]
            if not gf:
                s["groups"].append({"id": gid, "label": label, "count": 0, "total_area_km2": 0})
                continue
            gw, gh, _ = extent_km(gf)
            s["groups"].append({"id": gid, "label": label, "count": len(gf),
                                "total_area_km2": round(len(gf) * C.SQUARE_KM ** 2, 1),
                                "extent_km": {"width_ew": gw, "height_ns": gh}})
    s.update(extra)
    return s


def check_sizes(features):
    worst = 0.0
    for f in features:
        c = f["properties"]["corners"]
        (sw_lat, sw_lon), (se_lat, se_lon), (nw_lat, nw_lon) = c["SW"], c["SE"], c["NW"]
        for a in (GEOD.inv(sw_lon, sw_lat, se_lon, se_lat)[2], GEOD.inv(sw_lon, sw_lat, nw_lon, nw_lat)[2]):
            worst = max(worst, abs(a / 1000 - C.SQUARE_KM))
    return worst


# --------------------------------------------------------------------------- main
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ref = RefData()

    print("layer 1: port squares")
    l1 = layer_ports(ref)
    print("layer 2: port sea blocks")
    l2 = layer_sea_blocks(ref)
    print("layer 3: point square")
    l3 = layer_points(ref)
    print("layer 4: Thailand-Myanmar border")
    l4, land_km, sea_km, border_land, border_sea = layer_border(ref)

    all_feats = l1 + l2 + l3 + l4
    print(f"enriching {len(all_feats)} squares (geocode + elevation, cached) ...")
    if "--no-enrich" not in sys.argv:
        enrich_geocode(all_feats)
        enrich_elevation(all_feats)

    port_groups = [(p["id"], f"{p['name_th']} ({p['name_en']})") for p in C.PORTS]
    layers = [
        {"key": "ports", "title": "1. Port squares", "file": "layer1_ports.geojson", "features": l1,
         "summary": summarize(l1, port_groups)},
        {"key": "sea_blocks", "title": "2. Port sea blocks (30 x 30 km)", "file": "layer2_sea_blocks.geojson",
         "features": l2,
         "summary": summarize(l2, port_groups,
                              max_mainland_pct=round(C.SEA_MAX_MAINLAND_FRACTION * 100),
                              block_size_km=f"{C.SEA_BLOCK_ACROSS * C.SQUARE_KM:g} x "
                                            f"{C.SEA_BLOCK_OUT * C.SQUARE_KM:g}")},
        {"key": "points", "title": "3. Point 14.722987, 100.873950", "file": "layer3_point.geojson",
         "features": l3, "summary": summarize(l3)},
        {"key": "border", "title": "4. Thailand-Myanmar border", "file": "layer4_border.geojson",
         "features": l4,
         "summary": summarize(l4, border_length_km=round(land_km + sea_km, 1),
                              land_border_km=round(land_km, 1),
                              sea_extension_km=round(sea_km, 1),
                              sea_extension_offshore_km=C.BORDER_SEA_EXTENSION_KM,
                              maritime_squares=sum(f["properties"]["border_section"] == "maritime"
                                                   for f in l4),
                              step_mode=C.BORDER_STEP_MODE)},
    ]

    for L in layers:
        fc = {"type": "FeatureCollection", "name": L["key"], "features": L["features"]}
        (OUT / L["file"]).write_text(json.dumps(fc, ensure_ascii=False))
        s = L["summary"]
        print(f"  {L['title']}: {s['count']} squares, {s['total_area_km2']} km2 "
              f"(covered {s['covered_area_km2']} km2), extent {s['extent_km']['width_ew']} x "
              f"{s['extent_km']['height_ns']} km, max side error {check_sizes(L['features']) * 1000:.1f} m")
    worst = max(f["properties"]["mainland_pct"] for f in l2)
    print(f"  sea blocks: max mainland overlap {worst}%")

    bundle = {
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "ports": C.PORTS,
        "points": C.POINTS,
        "border_line_land": border_land,
        "border_line_sea": border_sea,
        "layers": [{k: L[k] for k in ("key", "title", "file", "summary")}
                   | {"geojson": {"type": "FeatureCollection", "features": L["features"]}} for L in layers],
    }
    (OUT / "layers.js").write_text("window.GIS_DATA = " + json.dumps(bundle, ensure_ascii=False) + ";\n")
    print(f"wrote {OUT / 'layers.js'}")


if __name__ == "__main__":
    main()
