from datetime import datetime, timedelta
import os
import urllib.parse
import glob
import requests
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from icrawler.builtin import BingImageCrawler

app = FastAPI(title="Sistema de Geolocalización y Rastreo Táctico")

DIR_ASSETS_AVIONES = os.path.join("static", "assets", "aviones")
os.makedirs(DIR_ASSETS_AVIONES, exist_ok=True)

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/api/flights")
def get_flights(lat: float = -34.4167, lon: float = -58.6500):
    try:
        url = f"https://api.adsb.lol/v2/lat/{lat}/lon/{lon}/dist/250"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=4)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        print(f"Error consultando adsb.lol: {e}")
    return {"ac": []}

@app.get("/api/search")
def search_location(q: str = Query(...)):
    try:
        if "," in q:
            partes = q.split(",")
            lat_val = float(partes[0].strip())
            lon_val = float(partes[1].strip())
            return {
                "lat": lat_val,
                "lon": lon_val,
                "display_name": f"Coordenadas manuales [{lat_val}, {lon_val}]"
            }

        url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(q)}&format=json&limit=1"
        headers = {"User-Agent": "GeolocalizadorTactico/12.9"}
        response = requests.get(url, headers=headers, timeout=4)
        data = response.json()
        if data:
            return {
                "lat": float(data[0]["lat"]),
                "lon": float(data[0]["lon"]),
                "display_name": data[0]["display_name"]
            }
    except Exception as e:
        print(f"Error en búsqueda geográfica: {e}")
    return {"error": "No encontrado"}

@app.get("/api/elevation")
def get_elevation(lat: float = None, lon: float = None, locations: str = None):
    try:
        loc_str = locations if locations else (f"{lat},{lon}" if lat and lon else None)
        if not loc_str:
            return {"elevation_m": 0, "elevation_ft": 0, "results": []}

        res = requests.get(f"https://api.open-elevation.com/api/v1/lookup?locations={loc_str}", timeout=4)
        if res.status_code == 200:
            data = res.json()
            if "results" in data and len(data["results"]) > 0:
                results = [{"elevation_m": r["elevation"], "elevation_ft": round(r["elevation"] * 3.28084)} for r in data["results"]]
                if locations:
                    return {"results": results}
                return results[0]
    except Exception as e:
        print(f"Error consultando elevación: {e}")
    return {"elevation_m": 0, "elevation_ft": 0, "results": []}

@app.get("/api/photo")
def get_aircraft_photo(reg: str = "N/A", model: str = "N/A"):
    mat_limpia = str(reg).strip().upper()
    mod_limpio = str(model).strip().upper()
    
    if not mat_limpia or mat_limpia in ["N/A", "UNKNOWN", "NONE"]:
        archivo_busqueda = mod_limpio if mod_limpio and mod_limpio != "N/A" else "AIRLINER"
    else:
        archivo_busqueda = mat_limpia

    archivo_limpio_str = "".join(c for c in archivo_busqueda if c.isalnum() or c in ("_", "-"))
    ruta_relativa = f"/static/assets/aviones/{archivo_limpio_str}.png"
    ruta_absoluta = os.path.join("static", "assets", "aviones", f"{archivo_limpio_str}.png")

    if os.path.exists(ruta_absoluta) and os.path.getsize(ruta_absoluta) > 2000:
        return {"url": ruta_relativa}

    try:
        temp_dir = os.path.join("static", "assets", "aviones", "temp_crawl")
        os.makedirs(temp_dir, exist_ok=True)
        
        terminos = [f"{mat_limpia} aircraft airplane", f"{mod_limpio} airliner plane", f"{archivo_busqueda} aircraft"]
        for term in terminos:
            try:
                crawler = BingImageCrawler(storage={'root_dir': temp_dir}, log_level='CRITICAL')
                crawler.crawl(keyword=term, max_num=1, file_idx_offset=0)
                archivos = glob.glob(os.path.join(temp_dir, "*.*"))
                if archivos:
                    import shutil
                    shutil.move(archivos[0], ruta_absoluta)
                    for f in glob.glob(os.path.join(temp_dir, "*.*")):
                        try: os.remove(f)
                        except: pass
                    break
            except:
                pass
        try: os.rmdir(temp_dir)
        except: pass
    except Exception as e:
        print(f"Error en crawler Bing: {e}")

    if os.path.exists(ruta_absoluta):
        return {"url": ruta_relativa}
    
    return {"url": ""}

@app.get("/", response_class=HTMLResponse)
@app.get("/app", response_class=HTMLResponse)
def get_web_app():
    fecha_nasa = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    fecha_night = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
    
    html_content = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>SISTEMA DE GEOLOCALIZACIÓN Y RASTREO TÁCTICO // MÓDULO WEB</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        :root {
            --fluor-green: #00ff66;
            --fluor-glow: 0 0 8px rgba(0, 255, 102, 0.5);
            --bg-dark: #0b0f19;
            --panel-bg: #1a1b26;
        }

        body {
            margin: 0;
            background-color: var(--bg-dark);
            color: var(--fluor-green);
            font-family: 'Consolas', monospace;
            display: flex;
            flex-direction: column;
            height: 100vh;
            overflow: hidden;
            text-shadow: var(--fluor-glow);
        }
        #header {
            text-align: center;
            padding: 8px;
            font-weight: bold;
            font-size: 14px;
            background: var(--bg-dark);
            border-bottom: 1px solid var(--fluor-green);
        }
        #control-panel {
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 6px 10px;
            background: var(--bg-dark);
            gap: 10px;
            border-bottom: 1px solid var(--fluor-green);
            flex-wrap: wrap;
            font-size: 12px;
        }
        .toolbar-group {
            display: flex;
            align-items: center;
            gap: 4px;
        }
        input, button {
            background: var(--panel-bg);
            color: var(--fluor-green);
            border: 1px solid var(--fluor-green);
            padding: 4px 8px;
            font-family: 'Consolas', monospace;
            font-weight: bold;
            cursor: pointer;
            font-size: 11px;
            box-shadow: var(--fluor-glow);
        }
        input { width: 180px; }
        .speed-input { width: 50px; text-align: center; }
        button:hover { background: var(--fluor-green); color: var(--bg-dark); }
        .btn-active { background: var(--fluor-green); color: var(--bg-dark) !important; }
        
        #main-container {
            display: flex;
            flex-grow: 1;
            padding: 8px;
            gap: 8px;
            height: calc(100vh - 110px);
            position: relative;
        }
        #map {
            flex-grow: 1;
            height: 100%;
            border: 2px solid var(--fluor-green);
            position: relative;
            box-shadow: var(--fluor-glow);
        }
        
        #radar-sweep-container {
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            pointer-events: none;
            overflow: hidden;
            z-index: 1000;
            display: none;
        }
        .radar-sweep {
            position: absolute;
            top: 50%; left: 50%;
            width: 250vw; height: 250vw;
            transform: translate(-50%, -50%);
            background: conic-gradient(from 0deg at 50% 50%, rgba(0, 255, 102, 0) 0deg, rgba(0, 255, 102, 0) 280deg, rgba(0, 255, 102, 0.4) 360deg);
            border-radius: 50%;
        }

        #side-panel {
            width: 340px;
            background: var(--panel-bg);
            border: 2px solid var(--fluor-green);
            padding: 15px;
            box-sizing: border-box;
            font-size: 12px;
            overflow-y: auto;
            line-height: 1.4;
            box-shadow: var(--fluor-glow);
        }
        #footer-status {
            background: #000000;
            border-top: 1px solid var(--fluor-green);
            padding: 6px 15px;
            font-size: 11px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            color: var(--fluor-green);
            font-family: 'Courier New', Courier, monospace;
        }
        .credits {
            color: var(--fluor-green);
            font-size: 11px;
            font-weight: bold;
            text-shadow: var(--fluor-glow);
            letter-spacing: 0.5px;
        }
        .credits a {
            color: var(--fluor-green);
            text-decoration: underline;
        }
        .credits a:hover {
            color: #ffffff;
        }
        
        .leaflet-popup-content-wrapper, .leaflet-popup-tip {
            background-color: var(--panel-bg) !important;
            color: var(--fluor-green) !important;
            border: 1px solid var(--fluor-green);
            font-family: 'Consolas', monospace;
            box-shadow: var(--fluor-glow);
        }
    </style>
</head>
<body>

    <div id="header">[ SISTEMA DE GEOLOCALIZACIÓN Y RASTREO TÁCTICO // MÓDULO NAVAL & AÉREO ]</div>
    
    <div id="control-panel">
        <div class="toolbar-group">
            <label>OBJ:</label>
            <input type="text" id="targetInput" placeholder="Ej: Tokyo o Coordenadas">
            <button onclick="buscarObjetivo()">RASTREAR</button>
        </div>
        <div class="toolbar-group">
            <span>Mapas:</span>
            <button onclick="cambiarCapa('osm')" id="btn-osm">OSM</button>
            <button onclick="cambiarCapa('topo')" id="btn-topo">Topo</button>
            <button onclick="cambiarCapa('sat')" id="btn-sat" class="btn-active">🛰 Sat</button>
            <button onclick="cambiarCapa('dark')" id="btn-dark">⬛ Dark</button>
            <button onclick="cambiarCapa('nasa')" id="btn-nasa">NASA</button>
            <button onclick="cambiarCapa('incendios')" id="btn-incendios">Térmico</button>
            <button onclick="cambiarCapa('nocturna')" id="btn-nocturna">Nocturna</button>
        </div>
        <div class="toolbar-group">
            <span>Filtros:</span>
            <button onclick="toggleFiltroEstado('asc')" id="btn-filtro-asc">▲ Asc</button>
            <button onclick="toggleFiltroEstado('cru')" id="btn-filtro-cru">■ Cru</button>
            <button onclick="toggleFiltroEstado('des')" id="btn-filtro-des">▼ Des</button>
        </div>
        <div class="toolbar-group">
            <span>Vel:</span>
            <input type="number" id="minVel" class="speed-input" value="0" oninput="aplicarFiltros()">
            <span>-</span>
            <input type="number" id="maxVel" class="speed-input" value="5000" oninput="aplicarFiltros()">
        </div>
        <div class="toolbar-group">
            <span>Operaciones:</span>
            <button onclick="escanearAviones()">✈ Radar</button>
            <button onclick="toggleRadarSweep()" id="btn-sweep">📡 Barrido</button>
            <button onclick="togglePredictiveVectors()" id="btn-predict" class="btn-active">🔮 GeminiPredict Pro</button>
            <button onclick="toggleClima()" id="btn-clima">🌧 Clima</button>
        </div>
    </div>

    <div id="main-container">
        <div id="map">
            <div id="radar-sweep-container">
                <div class="radar-sweep" id="sweep-element"></div>
            </div>
        </div>
        <div id="side-panel">
            <b style="color: var(--fluor-green); font-size: 13px;">[ PANEL TÁCTICO FLUOR ]</b><br><br>
            Selecciona una aeronave en vuelo para activar GeminiPredict Pro HUD con probabilidades dinámicas en verde flúor total.
        </div>
    </div>

    <div id="footer-status">
        <span id="status-text">Estado: Sistema listo. Colores dinámicos restaurados (Azul / Naranja / Verde).</span>
        <span class="credits">
            Algo que entendemos nosotros <a href="https://instagram.com/hax0redpr0" target="_blank">hax0redpr0</a> Support <a href="https://gemini.google.com" target="_blank">Gemini by Google</a> // <span style="color: #ffffff;">This is my design!</span>
        </span>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        const map = L.map('map', { minZoom: 2, maxZoom: 19 }).setView([-34.4167, -58.6500], 11);

        setTimeout(() => { map.invalidateSize(); }, 200);
        window.addEventListener('resize', () => { map.invalidateSize(); });

        const layers = {
            osm: L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap' }),
            topo: L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', { maxZoom: 17, attribution: 'OpenTopoMap' }),
            sat: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxZoom: 18, attribution: 'Esri World Imagery' }),
            dark: L.tileLayer('https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', { maxZoom: 16, attribution: 'Esri Dark Gray' }),
            nasa: L.tileLayer('https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/MODIS_Terra_CorrectedReflectance_TrueColor/default/FECHA_NASA/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg', { minZoom: 6, maxZoom: 9, noWrap: true, bounds: [[-85, -180], [85, 180]], attribution: 'NASA GIBS' }),
            incendios: L.tileLayer('https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/MODIS_Terra_CorrectedReflectance_Bands721/default/FECHA_NASA/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg', { minZoom: 6, maxZoom: 9, noWrap: true, bounds: [[-85, -180], [85, 180]], attribution: 'NASA Thermal' }),
            nocturna: L.tileLayer('https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/VIIRS_CityLights_2012/default/FECHA_NIGHT/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpg', { minZoom: 3, maxZoom: 8, noWrap: true, bounds: [[-85, -180], [85, 180]], attribution: 'NASA City Lights' })
        };

        layers.sat.addTo(map);

        function cambiarCapa(tipo) {
            Object.values(layers).forEach(l => map.removeLayer(l));
            layers[tipo].addTo(map);

            if (tipo === 'nasa' || tipo === 'incendios') {
                map.setMinZoom(6); map.setMaxZoom(9);
                if (map.getZoom() > 9) map.setZoom(9);
                if (map.getZoom() < 6) map.setZoom(6);
            } else if (tipo === 'nocturna') {
                map.setMinZoom(3); map.setMaxZoom(8);
                if (map.getZoom() > 8) map.setZoom(8);
                if (map.getZoom() < 3) map.setZoom(3);
            } else {
                map.setMinZoom(2); map.setMaxZoom(19);
            }

            document.querySelectorAll('#control-panel button').forEach(b => {
                if(b.id.startsWith('btn-') && b.id !== 'btn-sweep' && b.id !== 'btn-clima' && b.id !== 'btn-predict' && !b.id.startsWith('btn-filtro-')) b.classList.remove('btn-active');
            });
            const btnTarget = document.getElementById(`btn-${tipo}`);
            if(btnTarget) btnTarget.classList.add('btn-active');
        }

        let weatherLayer = null;
        async function toggleClima() {
            const btn = document.getElementById('btn-clima');
            if (weatherLayer) {
                map.removeLayer(weatherLayer);
                weatherLayer = null;
                btn.classList.remove('btn-active');
                document.getElementById('status-text').innerText = "Estado: Radar meteorológico desactivado.";
                return;
            }
            document.getElementById('status-text').innerText = "Estado: Conectando al radar meteorológico global...";
            try {
                const response = await fetch('https://api.rainviewer.com/public/weather-maps.json');
                const data = await response.json();
                if (data && data.radar && data.radar.past && data.radar.past.length > 0) {
                    const latestRadar = data.radar.past[data.radar.past.length - 1];
                    weatherLayer = L.tileLayer(data.host + latestRadar.path + '/256/{z}/{x}/{y}/2/1_1.png', {
                        tileSize: 256, opacity: 0.75, attribution: 'RainViewer.com', maxZoom: 19
                    }).addTo(map);
                    btn.classList.add('btn-active');
                    document.getElementById('status-text').innerText = "Estado: Radar meteorológico activo en tiempo real.";
                }
            } catch (err) {
                console.error("Error al cargar radar meteorológico:", err);
                document.getElementById('status-text').innerText = "Estado: Error al conectar con el radar meteorológico.";
            }
        }

        let sweepActive = false, sweepAngle = 0, sweepInterval = null;
        let predictActive = true, predictiveConePolygon = null, hudMarkersGroup = L.layerGroup(), hudLinesGroup = L.layerGroup();
        let predictTimeSeconds = 180;

        let avionesRawData = [], avionesMarkers = [], searchMarker = null;
        let selectedFlightId = null, selectedFlightData = null, aircraftTrailsMap = {}, trailPolyline = null;
        let filtrosEstado = { asc: true, cru: true, des: true };

        function toggleFiltroEstado(tipo) {
            filtrosEstado[tipo] = !filtrosEstado[tipo];
            const btn = document.getElementById(`btn-filtro-${tipo}`);
            if (filtrosEstado[tipo]) btn.classList.add('btn-active');
            else btn.classList.remove('btn-active');
            aplicarFiltros();
        }

        document.addEventListener("DOMContentLoaded", () => {
            ['asc', 'cru', 'des'].forEach(t => document.getElementById(`btn-filtro-${t}`).classList.add('btn-active'));
            hudMarkersGroup.addTo(map);
            hudLinesGroup.addTo(map);
        });

        map.on('click', (e) => {
            const latFixed = e.latlng.lat.toFixed(4);
            const lonFixed = e.latlng.lng.toFixed(4);
            document.getElementById('targetInput').value = `${latFixed}, ${lonFixed}`;
            document.getElementById('status-text').innerText = `Estado: Coordenadas capturadas [${latFixed}, ${lonFixed}]. Pulse RASTREAR.`;
        });

        function toggleRadarSweep() {
            sweepActive = !sweepActive;
            const container = document.getElementById('radar-sweep-container');
            const btn = document.getElementById('btn-sweep');
            if (sweepActive) {
                container.style.display = 'block';
                btn.classList.add('btn-active');
                if (!sweepInterval) {
                    sweepInterval = setInterval(() => {
                        sweepAngle = (sweepAngle + 2) % 360;
                        const sweepEl = document.getElementById('sweep-element');
                        if (sweepEl) sweepEl.style.transform = `translate(-50%, -50%) rotate(${sweepAngle}deg)`;
                        actualizarVisibilidadPorBarrido();
                    }, 25);
                }
            } else {
                container.style.display = 'none';
                btn.classList.remove('btn-active');
                if (sweepInterval) { clearInterval(sweepInterval); sweepInterval = null; }
                avionesMarkers.forEach(item => { if (item.marker && item.marker.getElement()) item.marker.getElement().style.opacity = '1'; });
            }
        }

        function togglePredictiveVectors() {
            predictActive = !predictActive;
            const btn = document.getElementById('btn-predict');
            
            if (predictActive) {
                btn.classList.add('btn-active');
                document.getElementById('status-text').innerText = "Estado: GeminiPredict Pro HUD activo [Cono Dinámico con Probabilidades al 100%].";
            } else {
                btn.classList.remove('btn-active');
                limpiarGeminiPredictLayers();
                document.getElementById('status-text').innerText = "Estado: GeminiPredict desactivado.";
            }
            actualizarPrediccionSeleccionada();
        }

        function limpiarGeminiPredictLayers() {
            if (predictiveConePolygon) { map.removeLayer(predictiveConePolygon); predictiveConePolygon = null; }
            hudMarkersGroup.clearLayers();
            hudLinesGroup.clearLayers();
        }

        async function actualizarPrediccionSeleccionada() {
            limpiarGeminiPredictLayers();
            if (!predictActive || !selectedFlightData) return;

            const ac = selectedFlightData;
            const velKts = ac.gs || 0;
            const velKmh = Math.round(velKts * 1.852);
            
            if (velKmh < 10 || !ac.lat || !ac.lon) {
                document.getElementById('status-text').innerText = "Estado: GeminiPredict Pro [Aeronave en tierra o detenida, sin vectores]";
                return;
            }

            const headingActual = ac.track || 0;
            const numPuntos = 25;
            let leftPoints = [], rightPoints = [];
            let distanciaTotalKm = (velKmh * (predictTimeSeconds / 3600.0));

            for (let i = 1; i <= numPuntos; i++) {
                const distanciaParcial = (i * (distanciaTotalKm / numPuntos));
                const leftRad = ((headingActual - 18) * Math.PI) / 180;
                const rightRad = ((headingActual + 18) * Math.PI) / 180;

                leftPoints.push([
                    ac.lat + (distanciaParcial * Math.cos(leftRad)) / 111.0,
                    ac.lon + (distanciaParcial * Math.sin(leftRad)) / (111.0 * Math.cos(ac.lat * Math.PI / 180))
                ]);
                rightPoints.unshift([
                    ac.lat + (distanciaParcial * Math.cos(rightRad)) / 111.0,
                    ac.lon + (distanciaParcial * Math.sin(rightRad)) / (111.0 * Math.cos(ac.lat * Math.PI / 180))
                ]);
            }

            const conePolygonCoords = [[ac.lat, ac.lon], ...leftPoints, ...rightPoints];
            predictiveConePolygon = L.polygon(conePolygonCoords, {
                color: '#00ff66',
                weight: 1,
                fillColor: '#00ff66',
                fillOpacity: 0.12,
                dashArray: '3, 3'
            }).addTo(map);

            const seed = Math.floor(velKmh + headingActual);
            let baseCentro = 60 + (seed % 21);
            let restante = 100 - baseCentro;
            let baseIzq = Math.floor(restante * 0.6);
            let baseDer = restante - baseIzq;

            const probCentro = baseCentro;
            const probIzq = baseIzq;
            const probDer = baseDer;

            const distCentro = distanciaTotalKm * 0.75;
            const distDesvio = distanciaTotalKm * 0.65;

            const radDir = (headingActual * Math.PI) / 180;
            const radIzq = ((headingActual - 12) * Math.PI) / 180;
            const radDer = ((headingActual + 12) * Math.PI) / 180;

            const latCentro = ac.lat + (distCentro * Math.cos(radDir)) / 111.0;
            const lonCentro = ac.lon + (distCentro * Math.sin(radDir)) / (111.0 * Math.cos(ac.lat * Math.PI / 180));

            const latIzq = ac.lat + (distDesvio * Math.cos(radIzq)) / 111.0;
            const lonIzq = ac.lon + (distDesvio * Math.sin(radIzq)) / (111.0 * Math.cos(ac.lat * Math.PI / 180));

            const latDer = ac.lat + (distDesvio * Math.cos(radDer)) / 111.0;
            const lonDer = ac.lon + (distDesvio * Math.sin(radDer)) / (111.0 * Math.cos(ac.lat * Math.PI / 180));

            const crearLineaPunteada = (destLat, destLon) => {
                L.polyline([[ac.lat, ac.lon], [destLat, destLon]], {
                    color: '#00ff66',
                    weight: 1.5,
                    opacity: 0.8,
                    dashArray: '4, 4'
                }).addTo(hudLinesGroup);
            };

            crearLineaPunteada(latCentro, lonCentro);
            crearLineaPunteada(latIzq, lonIzq);
            crearLineaPunteada(latDer, lonDer);

            const crearHudBadge = (lat, lon, texto) => {
                const icon = L.divIcon({
                    html: `<div style="background: rgba(26, 27, 38, 0.92); color: #00ff66; border: 1px solid #00ff66; font-size: 10px; padding: 2px 6px; font-family: 'Consolas', monospace; font-weight: bold; text-shadow: 0 0 5px #00ff66; box-shadow: 0 0 8px rgba(0,255,102,0.4); white-space: nowrap;">${texto}</div>`,
                    className: 'hud-badge-icon', iconSize: [70, 20], iconAnchor: [35, 10]
                });
                return L.marker([lat, lon], { icon: icon, interactive: false }).addTo(hudMarkersGroup);
            };

            crearHudBadge(latCentro, lonCentro, `▲ RECTO ${probCentro}%`);
            crearHudBadge(latIzq, lonIzq, `◄ IZQ ${probIzq}%`);
            crearHudBadge(latDer, lonDer, `DER ${probDer}% ►`);

            document.getElementById('status-text').innerText = `Estado: GeminiPredict Pro HUD [Activo] -> Vel: ${velKmh} km/h | Recto: ${probCentro}% | Izq: ${probIzq}% | Der: ${probDer}% (Total: 100%)`;
        }

        function actualizarVisibilidadPorBarrido() {
            if (!sweepActive) return;
            const centerPoint = map.latLngToContainerPoint(map.getCenter());
            avionesMarkers.forEach(item => {
                if (!item.marker || !item.marker.getElement()) return;
                const planePoint = map.latLngToContainerPoint(item.marker.getLatLng());
                let planeAngle = Math.atan2(planePoint.x - centerPoint.x, -(planePoint.y - centerPoint.y)) * (180 / Math.PI);
                if (planeAngle < 0) planeAngle += 360;
                let diff = (sweepAngle - planeAngle + 360) % 360;
                const elem = item.marker.getElement();
                if (diff >= 0 && diff <= 45) elem.style.opacity = Math.max(0.15, 1 - (diff / 45));
                else elem.style.opacity = '0.05';
            });
        }

        function mostrarTelemetria(ac) {
            selectedFlightData = ac; 
            const callsign = ac.flight ? ac.flight.trim() : (ac.r || "AVIÓN");
            const matricula = ac.r || 'N/A';
            const modelo = ac.t || 'N/A';
            selectedFlightId = ac.hex || callsign;

            if (trailPolyline) { map.removeLayer(trailPolyline); trailPolyline = null; }
            if (aircraftTrailsMap[selectedFlightId] && aircraftTrailsMap[selectedFlightId].length > 0) {
                trailPolyline = L.polyline(aircraftTrailsMap[selectedFlightId], { color: '#00ff66', weight: 3, opacity: 0.8, dashArray: '4, 4' }).addTo(map);
            }
            
            const baroRate = parseInt(ac.baro_rate || 0);
            let estadoTexto = baroRate > 100 ? `▲ ASCENDIENDO (${baroRate} ft/min)` : (baroRate < -100 ? `▼ DESCENDIENDO (${Math.abs(baroRate)} ft/min)` : '■ CRUCERO');
            const velKts = ac.gs || 0, velKmh = Math.round(velKts * 1.852);

            document.getElementById('side-panel').innerHTML = `
                <b style="color: #00ff66; font-size: 13px; text-shadow: 0 0 8px rgba(0,255,102,0.6);">[ TELEMETRÍA DE AERONAVE ]</b><br><br>
                <div style="border: 1px solid #00ff66; background: #0b0f19; padding: 4px; margin-bottom: 10px; text-align: center; box-shadow: 0 0 5px rgba(0,255,102,0.3);">
                    <img id="aircraft-photo" src="" alt="Visual" style="width: 100%; height: 100px; object-fit: contain; background: #0b0f19; display: none;">
                    <div style="font-size: 9px; color: #00ff66; margin-top: 2px;">// REGISTRO VISUAL CRAWLER</div>
                </div>
                <b>Callsign:</b> ${callsign}<br><b>Matrícula:</b> ${matricula}<br><b>Modelo:</b> ${modelo}<br>
                <b>Estado:</b> ${estadoTexto}<br><b>Altitud:</b> ${ac.alt_baro === 'ground' ? 'En tierra' : `${ac.alt_baro || 'N/A'} ft`}<br>
                <b>Velocidad:</b> ${velKts} kts (${velKmh} km/h)<br><b>Rumbo:</b> ${ac.track || 0}°<br><b>Coords:</b><br>${ac.lat}, ${ac.lon}
            `;

            if (matricula !== 'N/A' || modelo !== 'N/A') {
                fetch(`/api/photo?reg=${encodeURIComponent(matricula)}&model=${encodeURIComponent(modelo)}`)
                    .then(res => res.json())
                    .then(data => {
                        const img = document.getElementById('aircraft-photo');
                        if (img && data.url) { img.src = `${data.url}?t=${new Date().getTime()}`; img.style.display = 'block'; }
                    });
            }
            actualizarPrediccionSeleccionada();
        }

        async function escanearAviones(targetLat = null, targetLon = null) {
            const center = (targetLat !== null && targetLon !== null) ? { lat: targetLat, lng: targetLon } : map.getCenter();
            document.getElementById('status-text').innerText = "Estado: Escaneando tráfico aéreo en el sector...";
            try {
                const response = await fetch(`/api/flights?lat=${center.lat}&lon=${center.lng}`);
                const data = await response.json();
                
                if (data.ac && Array.isArray(data.ac) && data.ac.length > 0) {
                    avionesRawData = data.ac.filter(ac => ac.lat && ac.lon);
                    avionesRawData.forEach(ac => {
                        const flightId = ac.hex || (ac.flight ? ac.flight.trim() : "AVIÓN");
                        if (!aircraftTrailsMap[flightId]) aircraftTrailsMap[flightId] = [];
                        const lastPoint = aircraftTrailsMap[flightId][aircraftTrailsMap[flightId].length - 1];
                        if (!lastPoint || lastPoint[0] !== ac.lat || lastPoint[1] !== ac.lon) {
                            aircraftTrailsMap[flightId].push([ac.lat, ac.lon]);
                            if (aircraftTrailsMap[flightId].length > 25) aircraftTrailsMap[flightId].shift();
                        }
                        if (selectedFlightId === flightId) selectedFlightData = ac;
                    });
                    aplicarFiltros();
                } else {
                    document.getElementById('status-text').innerText = "Estado: Micro-corte temporal de API, manteniendo posición previa en pantalla.";
                }
            } catch (err) { 
                console.error("Error al escanear tráfico aéreo:", err); 
            }
        }

        function aplicarFiltros() {
            avionesMarkers.forEach(item => map.removeLayer(item.marker));
            avionesMarkers = [];
            const minV = parseFloat(document.getElementById('minVel').value) || 0;
            const maxV = parseFloat(document.getElementById('maxVel').value) || 5000;
            let count = 0;

            avionesRawData.forEach(ac => {
                const baroRate = parseInt(ac.baro_rate || 0);
                let tipoEstado = 'cru';
                if (baroRate > 100) tipoEstado = 'asc';
                else if (baroRate < -100) tipoEstado = 'des';

                if (!filtrosEstado[tipoEstado]) return;
                const velKmh = Math.round((ac.gs || 0) * 1.852);
                if (velKmh < minV || velKmh > maxV) return;

                count++;
                const callsign = ac.flight ? ac.flight.trim() : (ac.r || "AVIÓN");
                const heading = ac.track || 0;
                const flightId = ac.hex || callsign;

                if (selectedFlightId === flightId && trailPolyline) {
                    map.removeLayer(trailPolyline);
                    if (aircraftTrailsMap[flightId]) {
                        trailPolyline = L.polyline(aircraftTrailsMap[flightId], { color: '#00ff66', weight: 3, opacity: 0.8, dashArray: '4, 4' }).addTo(map);
                    }
                }

                // Colores dinámicos originales: Azul para Ascenso, Naranja para Descenso, Verde Flúor para Crucero
                let colorIcono = '#00ff66';
                let colorBorde = '#00ff66';
                
                if (tipoEstado === 'asc') {
                    colorIcono = '#00aaff'; // Azul brillante
                    colorBorde = '#00aaff';
                } else if (tipoEstado === 'des') {
                    colorIcono = '#ff8800'; // Naranja brillante
                    colorBorde = '#ff8800';
                } else {
                    colorIcono = '#00ff66'; // Verde flúor
                    colorBorde = '#00ff66';
                }

                const planeIcon = L.divIcon({
                    html: `<div style="display: flex; align-items: center; white-space: nowrap;">
                             <span style="transform: rotate(${heading - 90}deg); display: inline-block; color: ${colorIcono}; font-size: 16px; text-shadow: 0 0 6px ${colorIcono}; font-weight: bold;">✈</span>
                             <span style="background: rgba(26, 27, 38, 0.9); color: ${colorIcono}; font-size: 10px; padding: 1px 4px; margin-left: 2px; border: 1px solid ${colorBorde}; font-family: 'Consolas', monospace; text-shadow: 0 0 4px ${colorIcono};">${velKmh} km/h</span>
                           </div>`,
                    className: 'plane-marker-icon', iconSize: [90, 24], iconAnchor: [12, 12]
                });

                const marker = L.marker([ac.lat, ac.lon], { icon: planeIcon, interactive: true }).addTo(map);
                marker.bindPopup(`<b>✈ ${callsign}</b><br>Velocidad: ${velKmh} km/h<br>Alt: ${ac.alt_baro || 'N/A'} ft`);
                marker.on('click', (e) => { L.DomEvent.stopPropagation(e); mostrarTelemetria(ac); });

                avionesMarkers.push({ marker: marker, data: ac });
            });

            actualizarPrediccionSeleccionada();
            document.getElementById('status-text').innerText = `Estado: Radar aéreo activo -> ${count} aeronaves mostradas [Colores dinámicos].`;
        }

        async function buscarObjetivo() {
            const query = document.getElementById('targetInput').value;
            if (!query) return;
            document.getElementById('status-text').innerText = `Estado: Buscando objetivo "${query}"...`;
            try {
                const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
                const data = await res.json();
                if (data.lat && data.lon) {
                    map.setView([data.lat, data.lon], 11);
                    setTimeout(() => { map.invalidateSize(); }, 200);
                    if (searchMarker) map.removeLayer(searchMarker);
                    searchMarker = L.marker([data.lat, data.lon]).addTo(map).bindPopup(`<b>Objetivo Fijado:</b><br>${data.display_name}`).openPopup();
                    await escanearAviones(data.lat, data.lon);
                }
            } catch (err) { alert("No se pudo resolver el objetivo."); }
        }

        setInterval(() => { if (typeof escanearAviones === 'function') escanearAviones(); }, 10000);
    </script>
</body>
</html>
    """
    return html_content.replace("FECHA_NASA", fecha_nasa).replace("FECHA_NIGHT", fecha_night)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)