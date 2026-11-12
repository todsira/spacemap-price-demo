"""Inputs for make_squares.py. Edit coordinates / directions here and re-run the build."""

SQUARE_KM = 10.0

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
SEA_BLOCK_ACROSS = 3  # 30 km wide, port at the middle
SEA_BLOCK_OUT = 3     # 30 km out to sea
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

# Item 4: Thailand-Myanmar border.
# "chebyshev": next square is centred where the border leaves the previous square,
#              so consecutive squares touch edge-to-edge without overlapping.
# "along":     a square every 10 km measured along the (winding) border line.
BORDER_STEP_MODE = "chebyshev"
# Past the end of the land border (head of the Kra River estuary) the squares continue along
# Natural Earth's TH-MM maritime border line until it is this far from the mainland.
# 22.2 km = 12 nautical miles (territorial sea). Set to 0 to stop at the land border.
BORDER_SEA_EXTENSION_KM = 22.2

# Region used to clip the land / country data (lon_min, lat_min, lon_max, lat_max)
REGION_BBOX = (92.0, 4.0, 110.0, 24.0)

# Build-time enrichment from free public APIs (results are cached in build/sources/)
USER_AGENT = "th-gis-squares/1.0 (demo map build)"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
OPENTOPODATA_URL = "https://api.opentopodata.org/v1"
