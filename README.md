# Thailand GIS Squares

A web map of Thailand and the surrounding countries that works like Google Maps and uses only free data and tools: Leaflet, OpenStreetMap, Natural Earth, Esri World Imagery and OpenTopoMap. It shows switchable layers of red **10 × 10 km squares**:

1. **Port squares**: one square centred on each of the 4 main ports: ท่าเรือแหลมฉบัง, ท่าเรือมาบตาพุด, ท่าเรือสัตหีบ and ท่าเรือน้ำลึกสงขลา.
2. **Port sea blocks**: a 30 × 30 km block of 3 × 3 squares for each port. The block extends 30 km out to sea and is 30 km wide, centred on the port. Each column of 3 squares slides along the seaward direction to sit as close to the mainland as possible, with each square overlapping the mainland by at most 10% (`SEA_MAX_MAINLAND_FRACTION`). Islands are ignored, and blocks may overlap (Sattahip / Map Ta Phut).
3. **Point square**: one square centred on 14.722987, 100.873950.
4. **Thailand–Myanmar border**: north-up squares centred on the border line, running from north to south, with about 5 km on each side of the line. Past the end of the land border, at the head of the Kra River estuary, the squares follow Natural Earth's maritime border line down the estuary and out to 12 nm (22.2 km, set by `sea_extension_km` in `BORDERS`) from the mainland.
5. **Thailand–Cambodia border**: built the same way as layer 4. The squares run from the Laos tripoint at the Emerald Triangle to the coast at Hat Lek, Trat, then follow Natural Earth's median line in the Gulf of Thailand to 12 nm offshore. The maritime boundary there is disputed, and the median line is only an indicator.
6. **Thailand–Laos border**: built the same way as layer 4. The squares run from the Golden Triangle to the Emerald Triangle, including the Mekong sections. The border is landlocked, so there is no sea extension.
7. **Thailand–Malaysia border**: built the same way, but running west to east. It starts 12 nm offshore on Natural Earth's median line in the Andaman Sea, crosses the land border at Satun/Perlis, and ends at the Golok river mouth at Tak Bai. Natural Earth has no maritime line on the Gulf of Thailand side, so the squares stop at the coast there.

Hovering over a square shows its location, province and district (in English and Thai), land/sea %, the countries it covers, elevation or water depth, and the distance to the coast or port. Clicking a square pins the details, including its corners and UTM coordinates. Each layer has a summary card showing the number of squares, total area, square size and the layer's overall extent. The base maps are street, satellite, topographic (with contours) and light grey. The overlays are contour lines, hillshade relief, labels, the border line and markers.

## Run

```
python3 -m http.server -d web 8000     # then open http://localhost:8000
```
(You can also open `web/index.html` directly, because the data is loaded from `web/data/layers.js`.)

## Deploy to Cloudflare

The site is fully static. Everything it needs is in `web/`, including the generated data, so there is no build step. `wrangler.toml` deploys it as a Cloudflare **Worker with static assets**, using `[assets] directory = "./web"`.

**Git integration (deploys automatically on every push):**

1. In the Cloudflare dashboard, go to **Workers & Pages → Create → Import a repository**.
2. Pick `spacemap-price-demo`.
3. Set:
   - Build command: *(leave empty)*
   - Deploy command: `npx wrangler deploy`

**Direct upload from your machine:**

```
npx wrangler login
npx wrangler deploy
```

To preview locally with the same headers as production, run `npx wrangler dev`, then open http://localhost:8787.

Related files:
- `wrangler.toml` holds the Worker name and the assets directory. The `name` must match the Worker's name in the dashboard.
- `web/_headers` sets the security headers and caching. Data, scripts and styles are served with `Cache-Control: no-cache`, so browsers pick up a new deploy immediately but still reuse unchanged files (they get a quick "not modified" reply). The Content-Security-Policy only allows the map tile hosts the app uses: OpenStreetMap, OpenTopoMap and Esri. If you add a new base map, add its host to `img-src`.

## Rebuild the data

```
python3 -m venv .venv && .venv/bin/pip install -r build/requirements.txt
.venv/bin/python build/fetch_sources.py     # downloads OSM land polygons + Natural Earth (~30 MB)
.venv/bin/python build/make_squares.py      # add --no-enrich to skip the geocode/elevation API calls
```

To change the port coordinates, the seaward direction of each block, the mainland-overlap limit, the border stepping mode or the border layers (`BORDERS`: which countries, how far out to sea), edit `build/config.py`.

Each square is built in a transverse Mercator projection centred on the square itself, so every side is 10.000 km on the ground. The build prints the largest side error, which is under 1 m.

The reverse-geocode results (Nominatim, 1 request per second) and the elevation results (OpenTopoData) are cached in `build/sources/`.

The files `web/data/layer*.geojson` are plain GeoJSON in EPSG:4326 and can be loaded straight into QGIS.
