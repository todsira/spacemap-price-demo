/* Thailand GIS Squares — Leaflet front end. Data comes from data/layers.js (window.GIS_DATA). */
(function () {
  const DATA = window.GIS_DATA;
  const RED = "#d7263d";

  const wide = window.matchMedia("(min-width: 701px)").matches;
  const PAD = wide ? { paddingTopLeft: [360, 20], paddingBottomRight: [20, 20] } : { padding: [20, 20] };
  const map = L.map("map", { zoomControl: false, minZoom: 4, maxZoom: 18, worldCopyJump: true })
    .fitBounds([[5.2, 96.5], [21.0, 106.5]], PAD);
  L.control.zoom({ position: "topright" }).addTo(map);
  L.control.scale({ position: "bottomright", metric: true, imperial: false }).addTo(map);

  // ------------------------------------------------------------------ base maps
  const BASEMAPS = {
    osm: {
      label: "Street map",
      layer: L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19, attribution: "© OpenStreetMap contributors",
      }),
    },
    satellite: {
      label: "Satellite",
      layer: L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
        maxZoom: 19, attribution: "Imagery © Esri, Maxar, Earthstar Geographics, GIS User Community",
      }),
    },
    topo: {
      label: "Topographic",
      layer: L.tileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", {
        maxZoom: 17, attribution: "© OpenStreetMap contributors, SRTM · style © OpenTopoMap (CC-BY-SA)",
      }),
    },
    light: {
      label: "Light",
      layer: L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
        maxZoom: 19, subdomains: "abcd", attribution: "© OpenStreetMap contributors © CARTO",
      }),
    },
  };

  let currentBase = null;
  const baseBox = document.getElementById("basemaps");
  function setBase(key) {
    if (currentBase) map.removeLayer(BASEMAPS[currentBase].layer);
    currentBase = key;
    BASEMAPS[key].layer.addTo(map).bringToBack();
    if (map._loaded) writeHash();
    baseBox.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.key === key));
  }
  Object.entries(BASEMAPS).forEach(([key, b]) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.dataset.key = key;
    btn.textContent = b.label;
    btn.onclick = () => setBase(key);
    baseBox.appendChild(btn);
  });
  // URL hash "#lat,lon,zoom/basemap" restores a view (and is kept up to date for sharing)
  const hm = location.hash.match(/^#(-?[\d.]+),(-?[\d.]+),(\d+)(?:\/(\w+))?/);
  if (hm) map.setView([+hm[1], +hm[2]], +hm[3]);
  setBase(hm && BASEMAPS[hm[4]] ? hm[4] : "osm");
  function writeHash() {
    const c = map.getCenter();
    history.replaceState(null, "", `#${c.lat.toFixed(4)},${c.lng.toFixed(4)},${map.getZoom()}/${currentBase}`);
  }
  map.on("moveend", writeHash);

  // ------------------------------------------------------------------ overlays
  map.createPane("relief").style.zIndex = 250;
  map.createPane("labels").style.zIndex = 450;
  map.getPane("labels").style.pointerEvents = "none";

  const contours = L.tileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", {
    pane: "relief", maxZoom: 17, opacity: 0.6,
    attribution: "Contours © OpenTopoMap (CC-BY-SA), SRTM",
  });
  const hillshade = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Elevation/World_Hillshade/MapServer/tile/{z}/{y}/{x}", {
    pane: "relief", maxZoom: 16, opacity: 0.45, attribution: "Hillshade © Esri",
  });
  const labels = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}", {
    pane: "labels", maxZoom: 19, attribution: "Labels © Esri",
  });
  const toLatLng = (line) => line.map(([lon, lat]) => [lat, lon]);
  const borderLine = L.layerGroup([
    L.polyline(toLatLng(DATA.border_line_land), { color: "#7a1fa2", weight: 2, dashArray: "6 4", interactive: false }),
    L.polyline(toLatLng(DATA.border_line_sea), { color: "#7a1fa2", weight: 2, dashArray: "2 5", interactive: false }),
  ]);
  const portMarkers = L.layerGroup(DATA.ports.map((p) =>
    L.marker([p.lat, p.lon], { icon: L.divIcon({ className: "port-icon", iconSize: [12, 12] }), zIndexOffset: 1000 })
      .bindTooltip(`<b>${p.name_th}</b><br>${p.name_en}<br>${fmtLL(p.lat, p.lon)}`, { direction: "top", offset: [0, -8] })
  ).concat(DATA.points.map((p) =>
    L.circleMarker([p.lat, p.lon], { radius: 4, color: "#0b3d91", weight: 2, fillColor: "#fff", fillOpacity: 1 })
      .bindTooltip(`<b>${p.name_en}</b>`, { direction: "top" })
  )));

  const OVERLAYS = [
    { label: "Contour lines (OpenTopoMap)", layer: contours, on: false },
    { label: "Hillshade relief", layer: hillshade, on: false },
    { label: "Place names & boundaries", layer: labels, on: false },
    { label: "TH–MM border line (Natural Earth)", layer: borderLine, on: true },
    { label: "Port & point markers", layer: portMarkers, on: true },
  ];
  const ovBox = document.getElementById("overlays");
  OVERLAYS.forEach((o) => {
    const lab = document.createElement("label");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = o.on;
    cb.onchange = () => (cb.checked ? o.layer.addTo(map) : map.removeLayer(o.layer));
    lab.append(cb, document.createTextNode(o.label));
    ovBox.appendChild(lab);
    if (o.on) o.layer.addTo(map);
  });
  document.getElementById("contour-opacity").oninput = (e) => contours.setOpacity(+e.target.value);

  // ------------------------------------------------------------------ helpers
  function fmtLL(lat, lon) {
    return `${Math.abs(lat).toFixed(5)}°${lat >= 0 ? "N" : "S"}, ${Math.abs(lon).toFixed(5)}°${lon >= 0 ? "E" : "W"}`;
  }
  const num = (v, d = 0) => Number(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  const LAYER_TAG = {
    ports: "Port square",
    sea_blocks: "Port sea block",
    points: "Point square",
    border: "TH–MM border square",
  };

  function placeLine(p) {
    const en = [p.subdistrict, p.district, p.province, p.country].filter(Boolean);
    const th = [p.subdistrict_th, p.district_th, p.province_th].filter(Boolean);
    const parts = [];
    if (en.length) parts.push(esc(en.join(", ")));
    if (th.length) parts.push(esc(th.join(" · ")));
    if (!en.length && p.sea_area) parts.push(esc(p.sea_area));
    return parts.join("<br>");
  }

  function rows(p, full) {
    const r = [];
    if (p.port_en) r.push(["Port", `${esc(p.port_th)}<br>${esc(p.port_en)}`]);
    r.push(["Centre", fmtLL(p.center_lat, p.center_lon)]);
    r.push(["Size", `${p.size_km} km · ${num(p.area_km2)} km²`]);
    if (p.mainland_pct != null) {
      r.push(["Surface", `${p.mainland_pct}% mainland · ${p.island_pct}% islands · ${p.sea_pct}% sea`]);
    } else {
      r.push(["Surface", `${p.land_pct}% land · ${p.sea_pct}% sea`]);
    }
    if (p.sea_area && p.sea_pct > 0) r.push(["Sea area", esc(p.sea_area)]);
    const shares = Object.entries(p.country_share_pct || {});
    if (shares.length > 1) r.push(["Country split", shares.map(([k, v]) => `${esc(k)} ${v}%`).join(" · ")]);
    if (p.elevation_m != null) r.push(["Elevation", `${num(p.elevation_m)} m (SRTM, centre)`]);
    if (p.depth_m != null) r.push(["Water depth", `≈ ${num(p.depth_m)} m (GEBCO, centre)`]);
    r.push([p.surface === "land" ? "To coast" : "From coast", `${num(p.coast_dist_km, 1)} km`]);
    if (p.port_dist_km != null) r.push(["From port", `${num(p.port_dist_km, 1)} km ${p.seaward ? "(" + p.seaward + "ward block)" : ""}`]);
    if (p.block_row) r.push(["Block cell", `row ${p.block_row}, col ${p.block_col}`]);
    if (p.column_offset_km != null) {
      const t = p.column_offset_km;
      r.push(["Column shift", `${num(Math.abs(t), 2)} km ${t >= 0 ? "seaward" : "landward"} of the port line`]);
    }
    if (p.along_border_km != null) r.push(["Along border", `${num(p.along_border_km, 1)} km from northern end`]);
    if (p.border_section === "maritime") r.push(["Border type", "Maritime (Kra estuary / Andaman Sea)"]);
    if (full) {
      r.push(["UTM", `${p.utm_zone} · E ${num(p.utm_e)} · N ${num(p.utm_n)}`]);
      Object.entries(p.corners).forEach(([k, [la, lo]]) => r.push([`Corner ${k}`, fmtLL(la, lo)]));
    }
    return r.map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join("");
  }

  function infoHtml(p, full) {
    return `<div class="tip">
      <span class="tag">${LAYER_TAG[p.layer] || p.layer}</span>
      <h3>${esc(p.id)}</h3>
      <p class="place">${placeLine(p)}</p>
      <table>${rows(p, full)}</table>
      ${full ? "" : '<div class="hint">Click for corners &amp; UTM</div>'}
    </div>`;
  }

  // ------------------------------------------------------------------ square layers
  const baseStyle = { color: RED, weight: 2, fillColor: RED, fillOpacity: 0.22 };
  const hoverStyle = { weight: 3.5, fillOpacity: 0.45 };
  const cardsBox = document.getElementById("layer-cards");
  const squareLayers = {};

  DATA.layers.forEach((L0) => {
    const gj = L.geoJSON(L0.geojson, {
      style: () => baseStyle,
      onEachFeature: (f, lyr) => {
        lyr.bindTooltip(() => infoHtml(f.properties, false), { sticky: true, className: "sq-tip", direction: "auto", opacity: 1 });
        lyr.bindPopup(() => infoHtml(f.properties, true), { maxWidth: 340 });
        lyr.on("mouseover", () => { lyr.setStyle(hoverStyle); lyr.bringToFront(); });
        lyr.on("mouseout", () => lyr.setStyle(baseStyle));
      },
    }).addTo(map);
    squareLayers[L0.key] = gj;
    cardsBox.appendChild(makeCard(L0, gj));
  });

  function makeCard(L0, gj) {
    const s = L0.summary;
    const card = document.createElement("div");
    card.className = "card";
    const id = `cb-${L0.key}`;
    const stat = (k, v) => `<div class="stat"><div class="k">${k}</div><div class="v">${v}</div></div>`;
    let stats =
      stat("Red squares", num(s.count)) +
      stat("Total area", `${num(s.total_area_km2)} <small>km²</small>`) +
      stat("Each square", `${s.square_size_km} <small>km</small>`) +
      stat("Layer extent (W × H)", `${num(s.extent_km.width_ew, 1)} × ${num(s.extent_km.height_ns, 1)} <small>km</small>`);
    if (s.border_length_km) {
      stats += stat("Border length", `${num(s.border_length_km, 1)} <small>km</small>`);
      stats += stat("Land + maritime", `${num(s.land_border_km, 1)} + ${num(s.sea_extension_km, 1)} <small>km</small>`);
      stats += stat("Squares × 10 km", `${num(s.count * 10)} <small>km</small>`);
    }
    if (s.block_size_km) stats += stat("Block per port", `${s.block_size_km} <small>km</small>`);
    if (Math.abs(s.covered_area_km2 - s.total_area_km2) > 0.5) {
      stats += stat("Unique area (overlaps removed)", `${num(s.covered_area_km2, 1)} <small>km²</small>`);
    }

    let groups = "";
    if (s.groups) {
      groups = '<div class="groups">' + s.groups.map((g) => {
        return `<div data-group="${g.id}"><span>${esc(g.label)}</span><span>${g.count} · ${num(g.total_area_km2)} km²</span></div>`;
      }).join("") + "</div>";
    }
    let note = "";
    if (s.max_mainland_pct != null) {
      note = `<div class="note">Each column of 3 squares is slid as close to the mainland as possible, overlapping it by at most ${s.max_mainland_pct}%. Islands are ignored. Blocks may overlap (Sattahip / Map Ta Phut).</div>`;
    }
    if (s.step_mode === "chebyshev") {
      note = '<div class="note">North-up squares centred on the border line; each next square starts where the line leaves the previous one, so squares touch without overlapping.' +
        (s.sea_extension_km ? ` Past the land border the line follows the maritime border down the Kra estuary to ${num(s.sea_extension_offshore_km, 1)} km (12 nm) offshore (${s.maritime_squares} squares).` : "") + "</div>";
    }

    card.innerHTML = `
      <div class="card-head">
        <label for="${id}"><input type="checkbox" id="${id}" checked><span class="swatch"></span>${esc(L0.title)}</label>
        <button class="zoom-btn" type="button">Zoom</button>
      </div>
      <div class="stats">${stats}</div>${groups}${note}`;

    card.querySelector("input").onchange = (e) => {
      if (e.target.checked) gj.addTo(map); else map.removeLayer(gj);
      card.classList.toggle("off", !e.target.checked);
    };
    card.querySelector(".zoom-btn").onclick = () => {
      if (!map.hasLayer(gj)) card.querySelector("input").click();
      map.fitBounds(gj.getBounds(), { ...PAD, maxZoom: 11 });
    };
    card.querySelectorAll("[data-group]").forEach((el) => {
      el.onclick = () => {
        const b = L.latLngBounds([]);
        gj.eachLayer((l) => { if (l.feature.properties.group === el.dataset.group) b.extend(l.getBounds()); });
        if (b.isValid()) map.fitBounds(b, { ...PAD, maxZoom: 11 });
      };
    });
    return card;
  }

  // ------------------------------------------------------------------ mouse coordinates, panel toggle
  const coordsEl = document.getElementById("coords");
  map.on("mousemove", (e) => (coordsEl.textContent = `${fmtLL(e.latlng.lat, e.latlng.lng)} · z${map.getZoom()}`));

  const panel = document.getElementById("panel");
  const toggle = document.getElementById("panel-toggle");
  toggle.onclick = () => {
    const hidden = panel.classList.toggle("hidden");
    toggle.setAttribute("aria-expanded", !hidden);
  };
  if (window.matchMedia("(max-width: 700px)").matches) panel.classList.add("hidden");

  document.getElementById("foot").innerHTML =
    `Data built ${esc(DATA.generated)} · coastline: OSM land polygons · border &amp; countries: Natural Earth 10m · ` +
    "places: Nominatim · elevation: SRTM / GEBCO via OpenTopoData. GeoJSON files in <code>web/data/</code> open directly in QGIS.";
})();
