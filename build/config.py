"""Inputs for make_squares.py. Edit coordinates / directions here and re-run the build."""

SQUARE_KM = 10.0  # default size; the build generates every mode in MODES

# Main switch in the web app: the same layers built with different square sizes
MODES = [
    {"key": "optical", "label": "Hi Res Optical", "square_km": 10.0},
    {"key": "sar", "label": "Hi Res SAR", "square_km": 5.0},
]

# Square colours for layers 1-3 (layers 4-7 set theirs in BORDERS below). Chosen to stay
# distinct from each other and readable on the street, satellite and topographic maps,
# avoiding the greens of forest and the blues of sea.
LAYER_COLORS = {
    "ports": "#e11d48",       # 1. crimson
    "sea_blocks": "#f97316",  # 2. orange
    "points": "#eab308",      # 3. gold
}

# Item 1 + 2: main ports. Coordinates checked against OpenStreetMap (Nominatim).
# `seaward` is the cardinal direction the 30 x 30 km sea block extends towards.
PORTS = [
    {
        "id": "LCB",
        "name_th": "ท่าเรือแหลมฉบัง",
        "name_en": "Laem Chabang Port",
        "lat": 13.0734119,
        "lon": 100.8994177,
        "seaward": "W",
    },
    {
        "id": "MTP",
        "name_th": "ท่าเรือมาบตาพุด",
        "name_en": "Map Ta Phut Industrial Port",
        "lat": 12.6687770,
        "lon": 101.1547309,
        "seaward": "S",
    },
    {
        "id": "STH",
        "name_th": "ท่าเรือสัตหีบ",
        "name_en": "Sattahip Commercial Port (Chuk Samet)",
        "lat": 12.6272028,
        "lon": 100.9199841,
        "seaward": "S",
    },
    {
        "id": "SKA",
        "name_th": "ท่าเรือน้ำลึกสงขลา",
        "name_en": "Songkhla Deep Sea Port",
        "lat": 7.2280171,
        "lon": 100.5696920,
        "seaward": "E",
    },
]

# Item 2: sea block size (squares across x squares outward)
SEA_BLOCK_ACROSS = 3  # squares across, port at the middle (30 km wide at 10 km squares)
SEA_BLOCK_OUT = 3     # squares out to sea (30 km at 10 km squares, 15 km at 5 km)
# Each column of the block slides along the seaward direction to sit as close to the
# mainland as possible, while every square overlaps the mainland by at most this fraction.
# Islands are ignored (squares may cover them).
SEA_MAX_MAINLAND_FRACTION = 0.10
# Slide search range relative to the port line, km (negative = towards land)
SEA_SLIDE_RANGE_KM = (-15, 30)

# Item 3: single point of interest
POINTS = [
    {
        "id": "P1",
        "name_en": "Point 14.722987, 100.873950",
        "lat": 14.722987,
        "lon": 100.873950,
    },
]

# Items 4-7: border layers. Squares are north-up, centred on the Natural Earth land border,
# starting at its northern end (or western end with "start": "west"). Past the end of the land border at the coast, the squares
# continue along Natural Earth's maritime border line until it is `sea_extension_km` from the
# mainland (22.2 km = 12 nautical miles, territorial sea; 0 = stop at the land border).
BORDERS = [
    {
        "key": "border",
        "title": "4. Thailand-Myanmar border",
        "file": "layer4_border.geojson",
        "group": "TH-MM",
        "id_prefix": "BORDER",
        "countries": ("Thailand", "Myanmar"),
        "sea_extension_km": 22.2,
        "sea_label": "Kra estuary / Andaman Sea",
        "color": "#7c3aed",  # violet
        "start_label": "Golden Triangle (northern end)",
    },
    {
        "key": "border_kh",
        "title": "5. Thailand-Cambodia border",
        "file": "layer5_border_kh.geojson",
        "group": "TH-KH",
        "id_prefix": "BKH",
        "countries": ("Thailand", "Cambodia"),
        "sea_extension_km": 22.2,
        "sea_label": "Gulf of Thailand (median line; boundary is disputed)",
        "color": "#2563eb",  # blue
        "start_label": "Emerald Triangle (Laos tripoint)",
    },
    {
        "key": "border_la",
        "title": "6. Thailand-Laos border",
        "file": "layer6_border_la.geojson",
        "group": "TH-LA",
        "id_prefix": "BLA",
        "countries": ("Thailand", "Laos"),
        "sea_extension_km": 0,  # landlocked
        "sea_label": "",
        "color": "#0d9488",  # teal
        "start_label": "Golden Triangle (northern end)",
    },
    {
        "key": "border_my",
        "title": "7. Thailand-Malaysia border",
        "file": "layer7_border_my.geojson",
        "group": "TH-MY",
        "id_prefix": "BMY",
        "countries": ("Thailand", "Malaysia"),
        "start": "west",  # runs west -> east, from the Andaman Sea side to the Gulf of Thailand
        "sea_extension_km": 22.2,
        "sea_label": "Andaman Sea / Strait of Malacca (median line)",
        "color": "#c026d3",  # fuchsia
        "start_label": "12 nm offshore in the Andaman Sea (western end)",
    },
]

# Stepping rule for the border squares:
# "chebyshev": next square is centred where the border leaves the previous square,
#              so consecutive squares touch edge-to-edge without overlapping.
# "along":     a square every 10 km measured along the (winding) border line.
BORDER_STEP_MODE = "chebyshev"

# Region used to clip the land / country data (lon_min, lat_min, lon_max, lat_max)
REGION_BBOX = (92.0, 4.0, 110.0, 24.0)

# Build-time enrichment from free public APIs (results are cached in build/sources/)
USER_AGENT = "th-gis-squares/1.0 (demo map build)"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
OPENTOPODATA_URL = "https://api.opentopodata.org/v1"
