"""
Ticaretsim - Complete Game Builder
Reads src/index.html, extracts SVG + city coordinates, writes game.html
"""
import re, json, os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# 1. EXTRACT SVG + CITY COORDINATES
# ============================================================
src = os.path.join(ROOT, 'src', 'index.html')
with open(src, 'r', encoding='utf-8') as f:
    html = f.read()

svg_match = re.search(r'(<svg\b.*?</svg>)', html, re.DOTALL)
if not svg_match:
    print("ERROR: SVG not found"); sys.exit(1)
svg_content = svg_match.group(1)

def get_attr(tag_str, name):
    m = re.search(rf'{name}="([^"]*)"', tag_str)
    return m.group(1) if m else None

def extract_path_points(path_d):
    pts = []
    for m in re.finditer(r'M\s*(-?\d+(?:\.\d+)?)[,\s]+(-?\d+(?:\.\d+)?)', path_d):
        x, y = float(m.group(1)), float(m.group(2))
        if 0 <= x <= 1000 and 0 <= y <= 400:
            pts.append((x, y))
    if len(pts) <= 1:
        for m in re.finditer(r'L\s*(-?\d+(?:\.\d+)?)[,\s]+(-?\d+(?:\.\d+)?)', path_d):
            x, y = float(m.group(1)), float(m.group(2))
            if 0 <= x <= 1000 and 0 <= y <= 400:
                pts.append((x, y))
    return pts

cities_raw = {}
for region_match in re.finditer(
        r'<g\b[^>]*data-bolge="([^"]+)"[^>]*>(.*?)</g>\s*(?=<g\b[^>]*data-bolge=|</svg>)',
        html, re.DOTALL):
    region_name = region_match.group(1)
    region_content = region_match.group(2)
    for cg in re.finditer(r'<g\b([^>]*data-iladi="[^"]*"[^>]*)>(.*?)</g>', region_content, re.DOTALL):
        tag_attrs = cg.group(1)
        paths_content = cg.group(2)
        city_id = get_attr(tag_attrs, 'id')
        name    = get_attr(tag_attrs, 'data-iladi')
        plate   = get_attr(tag_attrs, 'data-plakakodu')
        if not city_id or not name:
            continue
        all_pts = []
        for d_attr in re.finditer(r'\bd="([^"]*)"', paths_content):
            all_pts.extend(extract_path_points(d_attr.group(1)))
        if not all_pts:
            for d_attr in re.finditer(r'\bd="([^"]*)"', paths_content):
                nums = re.findall(r'(-?\d+(?:\.\d+)?)', d_attr.group(1))
                if len(nums) >= 2:
                    all_pts.append((float(nums[0]), float(nums[1]))); break
        xs = [p[0] for p in all_pts]; ys = [p[1] for p in all_pts]
        cx = round((min(xs)+max(xs))/2, 1) if xs else 0
        cy = round((min(ys)+max(ys))/2, 1) if ys else 0
        base_id = city_id.replace('-asya','').replace('-avrupa','')
        clean_name = name.replace(' (Asya)','').replace(' (Avrupa)','')
        if base_id not in cities_raw:
            cities_raw[base_id] = {'name':clean_name,'region':region_name,
                                   'plate':int(plate) if plate else 0,
                                   'cx':cx,'cy':cy,'_xs':xs,'_ys':ys}
        else:
            cities_raw[base_id]['_xs'].extend(xs); cities_raw[base_id]['_ys'].extend(ys)
            ax=cities_raw[base_id]['_xs']; ay=cities_raw[base_id]['_ys']
            cities_raw[base_id]['cx']=round((min(ax)+max(ax))/2,1)
            cities_raw[base_id]['cy']=round((min(ay)+max(ay))/2,1)
for c in cities_raw.values():
    c.pop('_xs',None); c.pop('_ys',None)
print(f"Cities extracted: {len(cities_raw)}")

# ============================================================
# 2. ASSIGN PRODUCTION / DEMAND (game data)
# ============================================================
# Products: bugday, findik, turunçgil, tekstil, sanayi, petrol

REGION_PROD = {
    'Marmara':            {'sanayi':1,'tekstil':1},
    'Ege':                {'tekstil':2,'turunçgil':1},
    'Akdeniz':            {'turunçgil':2},
    'Karadeniz':          {'findik':2,'bugday':1},
    'İç Anadolu':         {'bugday':3},
    'Doğu Anadolu':       {},
    'Güneydoğu Anadolu':  {'petrol':1},
}
REGION_DEM = {
    'Marmara':            {'bugday':2,'findik':2,'turunçgil':1,'petrol':1},
    'Ege':                {'bugday':1,'sanayi':1,'petrol':2},
    'Akdeniz':            {'bugday':2,'sanayi':1,'tekstil':1},
    'Karadeniz':          {'sanayi':2,'tekstil':1},
    'İç Anadolu':         {'sanayi':1,'tekstil':1,'turunçgil':1},
    'Doğu Anadolu':       {'bugday':2,'tekstil':3,'sanayi':2},
    'Güneydoğu Anadolu':  {'bugday':2,'tekstil':2,'sanayi':2},
}
CITY_OVERRIDES = {
    'istanbul':    {'prod':{'sanayi':3,'tekstil':2}, 'dem':{'bugday':3,'findik':3,'turunçgil':2}},
    'kocaeli':     {'prod':{'sanayi':3},             'dem':{'bugday':2,'petrol':2}},
    'sakarya':     {'prod':{'tekstil':1},            'dem':{}},
    'ankara':      {'prod':{'bugday':2,'sanayi':1},  'dem':{'sanayi':3,'tekstil':2,'turunçgil':2}},
    'izmir':       {'prod':{'tekstil':2,'turunçgil':1},'dem':{'sanayi':2,'petrol':3,'findik':2}},
    'denizli':     {'prod':{'tekstil':3},            'dem':{}},
    'manisa':      {'prod':{'tekstil':1,'turunçgil':1},'dem':{}},
    'aydin':       {'prod':{'turunçgil':1,'tekstil':1},'dem':{}},
    'mugla':       {'prod':{'turunçgil':1},          'dem':{'sanayi':1}},
    'antalya':     {'prod':{'turunçgil':3},          'dem':{'sanayi':2,'tekstil':2,'bugday':2}},
    'mersin':      {'prod':{'turunçgil':2,'bugday':1},'dem':{'sanayi':2}},
    'adana':       {'prod':{'turunçgil':2,'bugday':2},'dem':{'sanayi':2}},
    'hatay':       {'prod':{'turunçgil':2},          'dem':{'sanayi':1}},
    'giresun':     {'prod':{'findik':3},             'dem':{'sanayi':2}},
    'ordu':        {'prod':{'findik':3},             'dem':{'sanayi':1}},
    'trabzon':     {'prod':{'findik':2},             'dem':{'sanayi':2,'tekstil':1}},
    'rize':        {'prod':{'findik':1},             'dem':{'sanayi':2}},
    'samsun':      {'prod':{'findik':1,'bugday':1},  'dem':{'sanayi':2,'tekstil':1}},
    'konya':       {'prod':{'bugday':3},             'dem':{'sanayi':2,'tekstil':2,'findik':2,'turunçgil':2}},
    'eskisehir':   {'prod':{'bugday':2,'tekstil':1}, 'dem':{'sanayi':2}},
    'kayseri':     {'prod':{'bugday':1,'tekstil':1}, 'dem':{'sanayi':2}},
    'sivas':       {'prod':{'bugday':2},             'dem':{'sanayi':2,'tekstil':1}},
    'batman':      {'prod':{'petrol':3},             'dem':{'bugday':2,'sanayi':2}},
    'diyarbakir':  {'prod':{'petrol':2},             'dem':{'bugday':2,'tekstil':2}},
    'adiyaman':    {'prod':{'petrol':2},             'dem':{'bugday':2,'tekstil':1}},
    'siirt':       {'prod':{'petrol':1},             'dem':{'bugday':2,'tekstil':2}},
    'sirnak':      {'prod':{'petrol':1},             'dem':{'bugday':2,'tekstil':2}},
    'sanliurfa':   {'prod':{},                       'dem':{'bugday':2,'tekstil':2,'sanayi':2,'petrol':1}},
    'gaziantep':   {'prod':{'tekstil':1},            'dem':{'bugday':2,'sanayi':2,'petrol':1}},
    'mardin':      {'prod':{},                       'dem':{'bugday':2,'tekstil':2,'sanayi':2}},
    'erzurum':     {'prod':{'bugday':1},             'dem':{'bugday':1,'tekstil':3,'sanayi':3}},
    'van':         {'prod':{},                       'dem':{'bugday':2,'tekstil':3,'sanayi':2}},
    'kars':        {'prod':{'bugday':1},             'dem':{'tekstil':2,'sanayi':2}},
    'agri':        {'prod':{},                       'dem':{'bugday':2,'tekstil':2,'sanayi':2}},
    'hakkari':     {'prod':{},                       'dem':{'bugday':2,'tekstil':3,'sanayi':3}},
}

for cid, city in cities_raw.items():
    reg = city['region']
    prod = dict(REGION_PROD.get(reg, {}))
    dem  = dict(REGION_DEM.get(reg, {}))
    if cid in CITY_OVERRIDES:
        prod.update(CITY_OVERRIDES[cid].get('prod', {}))
        dem.update(CITY_OVERRIDES[cid].get('dem', {}))
    city['prod'] = prod
    city['dem']  = dem

# ============================================================
# 3. BUILD CITIES JS OBJECT
# ============================================================
def build_cities_js(cities):
    lines = ['const CITIES = {']
    for cid, c in sorted(cities.items()):
        prod_s = json.dumps(c['prod'], ensure_ascii=False)
        dem_s  = json.dumps(c['dem'],  ensure_ascii=False)
        name_s = c['name'].replace("'", "\\'")
        region_s = c['region'].replace("'", "\\'")
        lines.append(f"  '{cid}': {{name:'{name_s}',region:'{region_s}',cx:{c['cx']},cy:{c['cy']},prod:{prod_s},dem:{dem_s}}},")
    lines.append('};')
    return '\n'.join(lines)

cities_js = build_cities_js(cities_raw)

# ============================================================
# 4. PATCH SVG: add game-relevant IDs and remove external CSS ref
# ============================================================
# Remove the external CSS link (we'll inline it)
# Add id="turkey-svg" for JS access, add markers group
svg_patched = svg_content
# Ensure svg has our ID
if 'id="svg-turkiye-haritasi"' in svg_patched:
    svg_patched = svg_patched.replace('id="svg-turkiye-haritasi"', 'id="turkey-svg"')

# ============================================================
# 5. WRITE GAME.HTML
# ============================================================
game_html = r"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>TicaretSim</title>
<script src="/socket.io/socket.io.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',sans-serif;background:#1a1a2e;color:#e0e0e0;height:100vh;display:flex;flex-direction:column;overflow:hidden}

/* HUD */
#hud{background:#16213e;border-bottom:2px solid #0f3460;padding:8px 16px;display:flex;align-items:center;gap:16px;flex-shrink:0;z-index:10}
#hud .logo{font-size:18px;font-weight:700;color:#e94560;letter-spacing:2px}
#hud .stat{display:flex;flex-direction:column;align-items:flex-start}
#hud .stat label{font-size:10px;color:#888;text-transform:uppercase;letter-spacing:1px}
#hud .stat span{font-size:14px;font-weight:600;color:#fff}
#hud .stat .money{color:#4ecca3}
#hud .sep{width:1px;height:36px;background:#0f3460;margin:0 4px}
#hud .spacer{flex:1}
#hud button{background:#0f3460;border:1px solid #4ecca3;color:#4ecca3;padding:6px 12px;border-radius:4px;cursor:pointer;font-size:12px;transition:all .2s}
#hud button:hover{background:#4ecca3;color:#16213e}

/* Travel progress bar */
#travel-bar{height:4px;background:#e94560;width:0%;transition:width 0.5s;position:fixed;top:0;left:0;z-index:100}

/* Main layout */
#game-wrap{display:flex;flex:1;overflow:hidden;position:relative}

/* Map */
#map-area{flex:1;position:relative;overflow:hidden;background:#0d1117}
#map-area svg{width:100%;height:100%;display:block}
/* Region colors */
#bolge-1 g path{fill:#2d6a8f}
#bolge-2 g path{fill:#6b4a8a}
#bolge-3 g path{fill:#8a5a2a}
#bolge-4 g path{fill:#4a6a4a}
#bolge-5 g path{fill:#7a6a2a}
#bolge-6 g path{fill:#8a3a3a}
#bolge-7 g path{fill:#5a3a6a}
#turkey-svg path{cursor:pointer;transition:fill .15s}
#turkey-svg path:hover{fill:#4ecca3!important;opacity:.9}
#turkey-svg .selected-city path{fill:#e94560!important}
/* Markers */
.marker{cursor:pointer;transition:transform .3s}
.marker-player{fill:#e94560;stroke:#fff;stroke-width:1.5}
.marker-npc{fill:#888;stroke:#ccc;stroke-width:1;opacity:.85}
.marker-npc:hover{fill:#bbb}

/* City panel */
#city-panel{width:300px;background:#16213e;border-left:2px solid #0f3460;display:flex;flex-direction:column;overflow-y:auto;flex-shrink:0;transition:transform .3s}
#city-panel.hidden{transform:translateX(100%);width:0;border:none;overflow:hidden}
#panel-header{background:#0f3460;padding:14px 16px;display:flex;justify-content:space-between;align-items:center}
#panel-header h2{font-size:16px;font-weight:700;color:#fff}
#panel-header .region-badge{font-size:11px;background:#1a1a2e;color:#888;padding:3px 8px;border-radius:10px}
#btn-close-panel{background:none;border:none;color:#888;font-size:18px;cursor:pointer;line-height:1}
#btn-close-panel:hover{color:#fff}
#panel-body{padding:14px;flex:1}
#panel-prices{margin-bottom:14px}
#panel-prices h3{font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px}
.price-row{display:flex;align-items:center;margin-bottom:8px;padding:8px;background:#1a1a2e;border-radius:6px;gap:8px}
.price-icon{font-size:18px;width:28px;text-align:center}
.price-info{flex:1}
.price-name{font-size:12px;color:#aaa}
.price-val{font-size:15px;font-weight:700;color:#4ecca3}
.price-trend{font-size:11px}
.price-trend.up{color:#e94560}
.price-trend.down{color:#4ecca3}
.price-controls{display:flex;align-items:center;gap:4px}
.qty-btn{background:#0f3460;border:1px solid #4ecca3;color:#4ecca3;width:22px;height:22px;border-radius:3px;cursor:pointer;font-size:14px;line-height:1;display:flex;align-items:center;justify-content:center}
.qty-btn:hover{background:#4ecca3;color:#16213e}
.qty-input{width:36px;text-align:center;background:#0d1117;border:1px solid #0f3460;color:#fff;border-radius:3px;padding:2px;font-size:12px}
.btn-buy,.btn-sell{font-size:11px;padding:3px 8px;border-radius:3px;cursor:pointer;border:1px solid;transition:all .2s}
.btn-buy{background:transparent;border-color:#4ecca3;color:#4ecca3}
.btn-buy:hover{background:#4ecca3;color:#16213e}
.btn-sell{background:transparent;border-color:#e94560;color:#e94560}
.btn-sell:hover{background:#e94560;color:#fff}
.btn-sell:disabled,.btn-buy:disabled{opacity:.3;cursor:not-allowed}
#panel-travel{border-top:1px solid #0f3460;padding-top:12px;margin-top:4px}
#btn-travel{width:100%;padding:12px;background:#e94560;border:none;color:#fff;font-size:14px;font-weight:700;border-radius:6px;cursor:pointer;transition:all .2s;letter-spacing:1px}
#btn-travel:hover{background:#c73652}
#btn-travel:disabled{background:#555;cursor:not-allowed}
#travel-time-display{text-align:center;font-size:12px;color:#888;margin-top:6px}
#travel-status{text-align:center;padding:20px;color:#888;font-style:italic}

/* Inventory bar */
#inventory-bar{background:#16213e;border-top:2px solid #0f3460;padding:8px 16px;display:flex;align-items:center;gap:12px;flex-shrink:0;min-height:52px}
#inventory-bar .inv-label{font-size:11px;color:#888;white-space:nowrap}
#inventory-items{display:flex;gap:8px;flex:1;flex-wrap:wrap}
.inv-item{background:#0f3460;border:1px solid #4ecca3;border-radius:6px;padding:4px 10px;font-size:12px;display:flex;align-items:center;gap:6px}
.inv-item .inv-name{color:#aaa}
.inv-item .inv-qty{color:#4ecca3;font-weight:700}

/* News ticker */
#news-area{background:#0d1117;border-top:1px solid #0f3460;padding:6px 16px;display:flex;align-items:center;gap:12px;flex-shrink:0}
#news-label{font-size:10px;color:#e94560;text-transform:uppercase;letter-spacing:2px;white-space:nowrap;font-weight:700}
#news-text{font-size:12px;color:#888;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;flex:1}

/* Notification toast */
#toast{position:fixed;bottom:80px;right:20px;background:#16213e;border:1px solid #4ecca3;color:#fff;padding:10px 16px;border-radius:6px;font-size:13px;opacity:0;transition:opacity .3s;pointer-events:none;z-index:1000;max-width:300px}
#toast.show{opacity:1}
#toast.error{border-color:#e94560;color:#e94560}

/* Capacity bar */
.cap-bar{height:6px;background:#0f3460;border-radius:3px;overflow:hidden;margin-top:4px}
.cap-fill{height:100%;background:#4ecca3;border-radius:3px;transition:width .3s}
.cap-fill.full{background:#e94560}

/* Chat panel */
#chat-panel{position:fixed;bottom:58px;right:16px;width:280px;background:#16213e;border:1px solid #0f3460;border-radius:10px;display:flex;flex-direction:column;z-index:200;transition:height .25s;height:320px;box-shadow:0 8px 32px rgba(0,0,0,.5)}
#chat-panel.collapsed{height:38px;overflow:hidden}
#chat-header{display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:#0f3460;border-radius:10px 10px 0 0;cursor:pointer;flex-shrink:0}
#chat-header span{font-size:12px;font-weight:700;color:#4ecca3}
#chat-online{font-size:11px;color:#888;margin-left:auto;margin-right:8px}
#chat-toggle{background:none;border:none;color:#888;cursor:pointer;font-size:14px;padding:0;line-height:1}
#chat-messages{flex:1;overflow-y:auto;padding:8px;display:flex;flex-direction:column;gap:4px}
.chat-msg{font-size:12px;line-height:1.4;word-break:break-word}
.chat-msg .chat-user{font-weight:700;color:#4ecca3;margin-right:4px}
.chat-msg .chat-user.me{color:#e94560}
.chat-msg .chat-ts{font-size:10px;color:#555;margin-left:4px}
.chat-msg.system{color:#888;font-style:italic}
#chat-input-row{display:flex;gap:6px;padding:8px;border-top:1px solid #0f3460;flex-shrink:0}
#chat-input{flex:1;background:#0d1117;border:1px solid #0f3460;color:#fff;padding:6px 10px;border-radius:4px;font-size:12px;outline:none}
#chat-input:focus{border-color:#4ecca3}
#chat-send{background:#0f3460;border:1px solid #4ecca3;color:#4ecca3;padding:6px 10px;border-radius:4px;cursor:pointer;font-size:12px;transition:all .2s}
#chat-send:hover{background:#4ecca3;color:#16213e}
</style>
</head>
<body>

<div id="travel-bar"></div>

<div id="hud">
  <div class="logo">TICARETSIM</div>
  <div class="sep"></div>
  <div class="stat"><label>Para</label><span id="hud-money" class="money">0 TL</span></div>
  <div class="sep"></div>
  <div class="stat"><label>Konum</label><span id="hud-location">—</span></div>
  <div class="sep"></div>
  <div class="stat"><label>Araç</label><span id="hud-capacity">0/20 ton</span></div>
  <div class="sep"></div>
  <div class="stat"><label>Oyuncu</label><span id="hud-username" style="color:#4ecca3">—</span></div>
  <div class="spacer"></div>
  <button onclick="window.location='/leaderboard'" style="border-color:#888;color:#888">🏆 Lider</button>
  <button id="btn-save" onclick="saveGame()">💾 Kaydet</button>
  <button onclick="logout()" style="border-color:#e94560;color:#e94560">Çıkış</button>
</div>

<div id="game-wrap">
  <div id="map-area">
    SVG_PLACEHOLDER
    <svg id="markers-svg" style="position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none"
         viewBox="0 0 1052.3622 744.09448" preserveAspectRatio="xMidYMid meet"></svg>
  </div>

  <div id="city-panel" class="hidden">
    <div id="panel-header">
      <div>
        <h2 id="panel-city-name">—</h2>
        <span class="region-badge" id="panel-region">—</span>
      </div>
      <button id="btn-close-panel" onclick="closeCityPanel()">✕</button>
    </div>
    <div id="panel-body">
      <div id="travel-status"></div>
      <div id="panel-prices">
        <h3>Pazar Fiyatları</h3>
        <div id="price-list"></div>
      </div>
      <div id="panel-travel">
        <button id="btn-travel" onclick="travelToSelected()">▶ Yola Çık</button>
        <div id="travel-time-display"></div>
      </div>
    </div>
  </div>
</div>

<div id="inventory-bar">
  <span class="inv-label">ENVANTER<br><span id="inv-cap-text" style="font-size:10px">0/20 ton</span></span>
  <div id="inventory-items"><span style="color:#555;font-size:12px">Boş</span></div>
</div>

<div id="news-area">
  <span id="news-label">HABER</span>
  <span id="news-text">Piyasalar açılıyor...</span>
</div>

<!-- Chat Panel -->
<div id="chat-panel" class="collapsed">
  <div id="chat-header" onclick="toggleChat()">
    <span>💬 Global Sohbet</span>
    <span id="chat-online">0 çevrimiçi</span>
    <button id="chat-toggle">▲</button>
  </div>
  <div id="chat-messages"></div>
  <div id="chat-input-row">
    <input id="chat-input" type="text" placeholder="Mesaj yaz..." maxlength="300"
           onkeydown="if(event.key==='Enter') sendChatMsg()"/>
    <button id="chat-send" onclick="sendChatMsg()">Gönder</button>
  </div>
</div>

<div id="toast"></div>

<script>
'use strict';
// ============================================================
// PRODUCTS
// ============================================================
const PRODUCTS = {
  bugday:    {name:'Buğday',       icon:'🌾', basePrice:800,  unit:'ton'},
  findik:    {name:'Fındık',       icon:'🌰', basePrice:4500, unit:'ton'},
  turunçgil: {name:'Turunçgil',    icon:'🍊', basePrice:1200, unit:'ton'},
  tekstil:   {name:'Tekstil',      icon:'👔', basePrice:2800, unit:'ton'},
  sanayi:    {name:'Sanayi Par.',  icon:'⚙️',  basePrice:6000, unit:'ton'},
  petrol:    {name:'Ham Petrol',   icon:'🛢️',  basePrice:3500, unit:'ton'}
};
const PRODUCT_IDS = Object.keys(PRODUCTS);

// ============================================================
// CITIES (auto-generated from SVG)
// ============================================================
CITIES_PLACEHOLDER

// ============================================================
// NPC DEFINITIONS
// ============================================================
const NPC_DEFS = [
  {id:'npc1',name:'Karadeniz Tüccarı', route:['giresun','istanbul'],   product:'findik',    amount:8},
  {id:'npc2',name:'Akdeniz Tüccarı',  route:['antalya','ankara'],     product:'turunçgil', amount:6},
  {id:'npc3',name:'Ege Tüccarı',      route:['denizli','kocaeli'],    product:'tekstil',   amount:7},
  {id:'npc4',name:'Sanayi Tüccarı',   route:['kocaeli','erzurum'],    product:'sanayi',    amount:5},
  {id:'npc5',name:'Güney Tüccarı',    route:['batman','izmir'],       product:'petrol',    amount:6},
];

// ============================================================
// NEWS EVENTS
// ============================================================
const NEWS_EVENTS = [
  {text:'Karadeniz bölgesinde fındık rekoltesi rekor kırdı!',  city:'giresun', prod:'findik',    delta:-0.2},
  {text:'İstanbul limanında grev başladı, tekstil ithalatı durdu!', city:'istanbul', prod:'tekstil', delta:0.25},
  {text:'Akdeniz\'de kuraklık, turunçgil hasatı düştü.',        city:'antalya',  prod:'turunçgil', delta:0.2},
  {text:'Kocaeli\'de fabrika yangını: sanayi parçası üretimi aksadı.', city:'kocaeli', prod:'sanayi', delta:0.3},
  {text:'Güneydoğu\'da boru hattı onarımı tamamlandı, petrol akışı arttı.', city:'batman', prod:'petrol', delta:-0.15},
  {text:'Konya\'da buğday mahsulü beklentilerin üzerinde çıktı.', city:'konya',   prod:'bugday',   delta:-0.2},
  {text:'Erzurum\'da şiddetli kış: tekstil talebi patladı!',     city:'erzurum', prod:'tekstil',  delta:0.2},
  {text:'Ankara\'da inşaat sektörü hız kazandı, sanayi talebi arttı.', city:'ankara', prod:'sanayi', delta:0.2},
  {text:'Gaziantep tekstil fuarı büyük ilgi gördü.',             city:'gaziantep', prod:'tekstil', delta:0.1},
  {text:'Van Gölü bölgesinde turizm patladı, gıda talebi arttı.', city:'van',    prod:'bugday',   delta:0.15},
];

// ============================================================
// SUPPLY STATE (per city per product, 1-13)
// ============================================================
let citySupply = {};

function initSupply() {
  Object.keys(CITIES).forEach(cid => {
    citySupply[cid] = {};
    PRODUCT_IDS.forEach(pid => {
      const prodLvl = (CITIES[cid].prod||{})[pid]||0;
      citySupply[cid][pid] = 5 + prodLvl;  // 5=neutral baseline
    });
  });
}

// ============================================================
// PRICE ENGINE
// ============================================================
let cachedPrices = {};

function calcPrice(cid, pid) {
  const base  = PRODUCTS[pid].basePrice;
  const sup   = citySupply[cid]?.[pid] ?? 5;
  const dem   = (CITIES[cid]?.dem||{})[pid]||0;
  const supF  = 1 - (sup - 5) * 0.04;   // 8→-12%, 2→+12%
  const demF  = 1 + dem * 0.15;         // dem:3 → +45%
  const noise = 0.88 + Math.random()*0.24;
  return Math.max(50, Math.round(base * supF * demF * noise));
}

function refreshPrices() {
  Object.keys(CITIES).forEach(cid => {
    cachedPrices[cid] = {};
    PRODUCT_IDS.forEach(pid => {
      cachedPrices[cid][pid] = calcPrice(cid, pid);
    });
    // Slow supply drift
    PRODUCT_IDS.forEach(pid => {
      const base = 5 + ((CITIES[cid].prod||{})[pid]||0);
      const cur  = citySupply[cid][pid];
      citySupply[cid][pid] = Math.max(1, Math.min(13,
        cur + (base - cur) * 0.1 + (Math.random()-0.5)*0.3));
    });
  });
}

// ============================================================
// GAME STATE
// ============================================================
let state = {
  money:         50000,
  position:      'ankara',
  inventory:     {},   // {pid: qty}
  truckCapacity: 20,
  traveling:     null, // {from,to,startTime,duration}
  selectedCity:  null,
  lastEcoTick:   0,
  lastNewsTime:  0,
};

function invLoad() {
  return Object.values(state.inventory).reduce((a,b)=>a+b,0);
}

// ============================================================
// TRAVEL
// ============================================================
const MAX_DIST   = 950;
const MAX_TRAVEL = 60000;  // ms

function cityDist(a, b) {
  const ca=CITIES[a], cb=CITIES[b];
  if(!ca||!cb) return MAX_DIST;
  return Math.hypot(ca.cx-cb.cx, ca.cy-cb.cy);
}

function travelDuration(a, b) {
  return Math.max(5000, Math.min(MAX_TRAVEL, (cityDist(a,b)/MAX_DIST)*MAX_TRAVEL));
}

function startTravel(target) {
  if (state.traveling) return;
  if (state.position === target) { showToast('Zaten buradasınız!'); return; }
  const dur = travelDuration(state.position, target);
  state.traveling = {from:state.position, to:target, startTime:Date.now(), duration:dur};
  state.selectedCity = null;
  closeCityPanel();
  updateHUD();
  showToast(`${CITIES[target]?.name||target}'e yola çıkıldı (${Math.round(dur/1000)}s)`);
}

function travelToSelected() {
  if (state.selectedCity) startTravel(state.selectedCity);
}

// ============================================================
// BUY / SELL
// ============================================================
function buyProduct(pid, qty) {
  qty = parseInt(qty)||0;
  if (qty <= 0) return;
  const price = cachedPrices[state.position]?.[pid];
  if (!price) return;
  const cost = price * qty;
  if (cost > state.money) return showToast('Yeterli para yok!','error');
  if (invLoad() + qty > state.truckCapacity) return showToast('Araç kapasitesi dolu!','error');
  state.money -= cost;
  state.inventory[pid] = (state.inventory[pid]||0) + qty;
  citySupply[state.position][pid] = Math.max(1, (citySupply[state.position][pid]||5) - qty*0.4);
  refreshCityPanel();
  updateHUD();
  updateInventoryBar();
  showToast(`${qty} ton ${PRODUCTS[pid].name} → ${cost.toLocaleString('tr-TR')} TL`);
  logTransaction('buy', pid, qty, price);
}

function sellProduct(pid, qty) {
  qty = parseInt(qty)||0;
  const have = state.inventory[pid]||0;
  if (qty <= 0 || have <= 0) return;
  qty = Math.min(qty, have);
  const price = cachedPrices[state.position]?.[pid];
  if (!price) return;
  const earn = price * qty;
  state.money += earn;
  state.inventory[pid] = have - qty;
  if (!state.inventory[pid]) delete state.inventory[pid];
  citySupply[state.position][pid] = Math.min(13, (citySupply[state.position][pid]||5) + qty*0.4);
  refreshCityPanel();
  updateHUD();
  updateInventoryBar();
  showToast(`Satıldı! +${earn.toLocaleString('tr-TR')} TL`);
  logTransaction('sell', pid, qty, price);
}

// ============================================================
// NPC SYSTEM
// ============================================================
let npcs = NPC_DEFS.map(d=>({...d,posIdx:0,position:d.route[0],traveling:null}));

function tickNPCs() {
  const now = Date.now();
  npcs.forEach(npc => {
    if (npc.traveling) {
      const t = (now - npc.traveling.startTime) / npc.traveling.duration;
      if (t >= 1) {
        npc.position = npc.traveling.to;
        npc.traveling = null;
        npcArrived(npc);
      }
    } else {
      const ri = npc.route.indexOf(npc.position);
      const ni = (ri+1) % npc.route.length;
      const dest = npc.route[ni];
      const dur  = travelDuration(npc.position, dest) * (0.8 + Math.random()*0.4);
      // At source (even index): buy → reduce supply
      if (ri % 2 === 0) {
        const src = npc.position;
        if (citySupply[src]?.[npc.product] !== undefined)
          citySupply[src][npc.product] = Math.max(1, citySupply[src][npc.product] - npc.amount*0.2);
      }
      npc.traveling = {startTime:now, duration:dur, from:npc.position, to:dest};
    }
  });
}

function npcArrived(npc) {
  const ri = npc.route.indexOf(npc.position);
  // At destination (odd index): sell → increase supply
  if (ri % 2 === 1) {
    if (citySupply[npc.position]?.[npc.product] !== undefined)
      citySupply[npc.position][npc.product] = Math.min(13,
        citySupply[npc.position][npc.product] + npc.amount*0.2);
  }
}

// ============================================================
// MARKERS (SVG overlay)
// ============================================================
let markersSvg = null;

function initMarkers() {
  markersSvg = document.getElementById('markers-svg');
}

function npcProgress(npc) {
  if (!npc.traveling) return null;
  return Math.min(1, (Date.now()-npc.traveling.startTime)/npc.traveling.duration);
}

function lerpCoord(a, b, t) {
  const ca=CITIES[a], cb=CITIES[b];
  if(!ca||!cb) return ca||{cx:500,cy:200};
  return {cx: ca.cx+(cb.cx-ca.cx)*t, cy: ca.cy+(cb.cy-ca.cy)*t};
}

function updateMarkers() {
  if (!markersSvg) return;
  markersSvg.innerHTML = '';

  // Player marker
  let pc;
  if (state.traveling) {
    const t = Math.min(1,(Date.now()-state.traveling.startTime)/state.traveling.duration);
    pc = lerpCoord(state.traveling.from, state.traveling.to, t);
  } else {
    pc = CITIES[state.position];
  }
  if (pc) {
    const g = svgEl('g');
    g.setAttribute('class','marker');
    const outer = svgEl('circle');
    outer.setAttribute('cx', pc.cx); outer.setAttribute('cy', pc.cy);
    outer.setAttribute('r','9'); outer.setAttribute('fill','#e94560');
    outer.setAttribute('opacity','0.3');
    const inner = svgEl('circle');
    inner.setAttribute('cx', pc.cx); inner.setAttribute('cy', pc.cy);
    inner.setAttribute('r','5'); inner.setAttribute('class','marker-player');
    g.appendChild(outer); g.appendChild(inner);
    markersSvg.appendChild(g);
  }

  // NPC markers
  npcs.forEach(npc => {
    let nc;
    const t = npcProgress(npc);
    if (t !== null) {
      nc = lerpCoord(npc.traveling.from, npc.traveling.to, t);
    } else {
      nc = CITIES[npc.position];
    }
    if (!nc) return;
    const circle = svgEl('circle');
    circle.setAttribute('cx', nc.cx); circle.setAttribute('cy', nc.cy);
    circle.setAttribute('r','4'); circle.setAttribute('class','marker-npc');
    circle.setAttribute('pointer-events','all');
    circle.setAttribute('style','cursor:pointer');
    const title = document.createElementNS('http://www.w3.org/2000/svg','title');
    title.textContent = `${npc.name} — ${PRODUCTS[npc.product].name}`;
    circle.appendChild(title);
    markersSvg.appendChild(circle);
  });
}

function svgEl(tag) {
  return document.createElementNS('http://www.w3.org/2000/svg', tag);
}

// ============================================================
// MAP EVENTS
// ============================================================
function setupMapEvents() {
  const svg = document.getElementById('turkey-svg');
  if (!svg) { console.error('SVG not found'); return; }
  svg.addEventListener('click', e => {
    const g = e.target.closest('[data-iladi]');
    if (!g) return;
    let cid = g.getAttribute('id');
    cid = cid.replace('-asya','').replace('-avrupa','');
    if (CITIES[cid]) openCityPanel(cid);
  });
  svg.addEventListener('mouseover', e => {
    const g = e.target.closest('[data-iladi]');
    if (g) g.style.opacity='0.85';
  });
  svg.addEventListener('mouseout', e => {
    const g = e.target.closest('[data-iladi]');
    if (g) g.style.opacity='';
  });
}

// ============================================================
// UI
// ============================================================
function openCityPanel(cid) {
  state.selectedCity = cid;
  document.getElementById('city-panel').classList.remove('hidden');
  refreshCityPanel();
}

function closeCityPanel() {
  state.selectedCity = null;
  document.getElementById('city-panel').classList.add('hidden');
}

function refreshCityPanel() {
  const cid = state.selectedCity;
  if (!cid || !CITIES[cid]) return;
  const city = CITIES[cid];
  document.getElementById('panel-city-name').textContent = city.name;
  document.getElementById('panel-region').textContent = city.region;

  // Travel button state
  const travelBtn = document.getElementById('btn-travel');
  const ttDisplay = document.getElementById('travel-time-display');
  const travelStatus = document.getElementById('travel-status');

  if (state.traveling) {
    const rem = Math.max(0, Math.ceil((state.traveling.startTime+state.traveling.duration-Date.now())/1000));
    travelStatus.textContent = `🚛 Yolda: ${CITIES[state.traveling.to]?.name} (${rem}s)`;
    travelBtn.disabled = true;
    travelBtn.textContent = '⏳ Yolda...';
  } else if (cid === state.position) {
    travelStatus.textContent = '📍 Şu an buradasınız';
    travelBtn.disabled = true;
    travelBtn.textContent = '▶ Buraya Git';
    ttDisplay.textContent = '';
  } else {
    travelStatus.textContent = '';
    travelBtn.disabled = false;
    travelBtn.textContent = `▶ ${city.name}'e Git`;
    const dur = Math.round(travelDuration(state.position, cid)/1000);
    ttDisplay.textContent = `⏱ Yolculuk süresi: ~${dur} saniye`;
  }

  // Price list
  const pl = document.getElementById('price-list');
  pl.innerHTML = '';
  PRODUCT_IDS.forEach(pid => {
    const p = PRODUCTS[pid];
    const price = cachedPrices[cid]?.[pid] || 0;
    const inInv  = state.inventory[pid]||0;

    const row = document.createElement('div');
    row.className = 'price-row';

    const prodLvl = (CITIES[cid].prod||{})[pid]||0;
    const demLvl  = (CITIES[cid].dem||{})[pid]||0;
    let trendHtml = '';
    if (prodLvl >= 2) trendHtml = `<span class="price-trend down">↓ üretim</span>`;
    else if (demLvl >= 2) trendHtml = `<span class="price-trend up">↑ talep</span>`;

    row.innerHTML = `
      <span class="price-icon">${p.icon}</span>
      <div class="price-info">
        <div class="price-name">${p.name}</div>
        <div class="price-val">${price.toLocaleString('tr-TR')} TL/${p.unit} ${trendHtml}</div>
      </div>
      <div class="price-controls">
        <input class="qty-input" id="qty-${pid}" type="number" min="1" max="${state.truckCapacity}" value="1"/>
        <button class="btn-buy" onclick="buyProduct('${pid}', document.getElementById('qty-${pid}').value)"
          ${state.traveling||cid!==state.position?'disabled':''}>AL</button>
        <button class="btn-sell" onclick="sellProduct('${pid}', document.getElementById('qty-${pid}').value)"
          ${state.traveling||cid!==state.position||!inInv?'disabled':''}>SAT</button>
      </div>`;
    pl.appendChild(row);
  });
}

function updateHUD() {
  document.getElementById('hud-money').textContent =
    Math.round(state.money).toLocaleString('tr-TR') + ' TL';
  document.getElementById('hud-location').textContent =
    state.traveling ? `🚛 → ${CITIES[state.traveling.to]?.name||'?'}` :
                      (CITIES[state.position]?.name || state.position);
  const load = invLoad();
  document.getElementById('hud-capacity').textContent =
    `${load}/${state.truckCapacity} ton`;
}

function updateInventoryBar() {
  const load = invLoad();
  document.getElementById('inv-cap-text').textContent = `${load}/${state.truckCapacity} ton`;
  const el = document.getElementById('inventory-items');
  const entries = Object.entries(state.inventory).filter(([,q])=>q>0);
  if (!entries.length) {
    el.innerHTML = '<span style="color:#555;font-size:12px">Boş</span>';
    return;
  }
  el.innerHTML = entries.map(([pid,qty])=>
    `<div class="inv-item"><span class="inv-name">${PRODUCTS[pid]?.icon} ${PRODUCTS[pid]?.name}</span><span class="inv-qty">×${qty}</span></div>`
  ).join('');
}

function showToast(msg, type='') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'show' + (type ? ' '+type : '');
  clearTimeout(t._tid);
  t._tid = setTimeout(()=>t.className='', 2800);
}

function showNews(text) {
  document.getElementById('news-text').textContent = text;
}

// ============================================================
// TRAVEL PROGRESS BAR + ANIMATION
// ============================================================
function updateTravelBar() {
  const bar = document.getElementById('travel-bar');
  if (!state.traveling) { bar.style.width='0%'; return; }
  const t = (Date.now()-state.traveling.startTime)/state.traveling.duration;
  bar.style.width = Math.min(100,t*100)+'%';
}

// ============================================================
// AUTH
// ============================================================
function getToken() { return localStorage.getItem('ts_token'); }
function getCurrentUser() {
  const raw = localStorage.getItem('ts_user');
  return raw ? JSON.parse(raw) : null;
}
function logout() {
  localStorage.removeItem('ts_token');
  localStorage.removeItem('ts_user');
  window.location.href = '/';
}
function authGuard() {
  if (!getToken()) { window.location.href = '/'; return false; }
  return true;
}

// ============================================================
// SAVE / LOAD (server-side)
// ============================================================
async function saveGame() {
  const token = getToken();
  if (!token) return;
  try {
    await fetch('/api/game/save', {
      method: 'POST',
      headers: {'Content-Type':'application/json','Authorization':'Bearer '+token},
      body: JSON.stringify({
        state: {...state, traveling: state.traveling ? {...state.traveling} : null},
        citySupply,
        npcs: npcs.map(n=>({...n, traveling: n.traveling ? {...n.traveling} : null}))
      })
    });
  } catch(e) { console.warn('Save failed', e); }
}

async function loadGame() {
  const token = getToken();
  if (!token) return false;
  try {
    const res = await fetch('/api/game/state', {
      headers: {'Authorization':'Bearer '+token}
    });
    if (!res.ok) return false;
    const data = await res.json();
    if (data.state) {
      Object.assign(state, data.state);
      Object.assign(citySupply, data.citySupply || {});
      if (data.npcs && data.npcs.length) npcs = data.npcs;
      return true;
    }
  } catch(e) { console.warn('Load failed', e); }
  return false;
}

async function logTransaction(action, pid, qty, price) {
  const token = getToken();
  if (!token) return;
  fetch('/api/game/transaction', {
    method: 'POST',
    headers: {'Content-Type':'application/json','Authorization':'Bearer '+token},
    body: JSON.stringify({cityId:state.position, productId:pid, action, quantity:qty, price, total:price*qty})
  }).catch(()=>{});
}

// ============================================================
// MAIN LOOP
// ============================================================
const ECO_INTERVAL  = 10 * 60 * 1000;  // 10 min
const NEWS_INTERVAL =  5 * 60 * 1000;  //  5 min

let lastFrame = 0;
function loop(ts) {
  requestAnimationFrame(loop);
  if (ts - lastFrame < 500) return;  // throttle to 2fps
  lastFrame = ts;

  const now = Date.now();

  // Economy tick
  if (now - state.lastEcoTick >= ECO_INTERVAL) {
    refreshPrices();
    state.lastEcoTick = now;
  }

  // News
  if (now - state.lastNewsTime >= NEWS_INTERVAL) {
    const ev = NEWS_EVENTS[Math.floor(Math.random()*NEWS_EVENTS.length)];
    showNews(ev.text);
    // Apply price modifier via supply change
    if (ev.city && ev.prod && citySupply[ev.city]) {
      const cur = citySupply[ev.city][ev.prod]||5;
      citySupply[ev.city][ev.prod] = Math.max(1, Math.min(13,
        cur * (1 - ev.delta)));
      cachedPrices[ev.city][ev.prod] = calcPrice(ev.city, ev.prod);
    }
    state.lastNewsTime = now;
  }

  // Travel completion
  if (state.traveling) {
    const t = (now-state.traveling.startTime)/state.traveling.duration;
    if (t >= 1) {
      state.position = state.traveling.to;
      state.traveling = null;
      updateHUD();
      openCityPanel(state.position);
      showToast(`${CITIES[state.position]?.name}'e varıldı!`);
    } else if (state.selectedCity === state.traveling.to ||
               state.selectedCity === state.traveling.from) {
      refreshCityPanel();
    }
  }

  tickNPCs();
  updateTravelBar();
  updateMarkers();
  if (state.selectedCity) refreshCityPanel();
}

// ============================================================
// INIT
// ============================================================
async function init() {
  if (!authGuard()) return;

  const user = getCurrentUser();
  if (user) document.getElementById('hud-username').textContent = user.username;

  initSupply();
  refreshPrices();

  const loaded = await loadGame();
  if (!loaded) {
    state.lastEcoTick  = Date.now();
    state.lastNewsTime = Date.now() - NEWS_INTERVAL + 5000;
  } else {
    if (!state.lastEcoTick)  state.lastEcoTick  = Date.now();
    if (!state.lastNewsTime) state.lastNewsTime = Date.now() - NEWS_INTERVAL + 5000;
    refreshPrices();
  }

  setupMapEvents();
  initMarkers();
  updateHUD();
  updateInventoryBar();
  updateMarkers();
  openCityPanel(state.position);
  requestAnimationFrame(loop);

  // Auto-save every 2 min
  setInterval(saveGame, 2*60*1000);

  initChat();
}

// ============================================================
// CHAT (Socket.io)
// ============================================================
let socket = null;
let chatCollapsed = true;

function toggleChat() {
  chatCollapsed = !chatCollapsed;
  document.getElementById('chat-panel').classList.toggle('collapsed', chatCollapsed);
  document.getElementById('chat-toggle').textContent = chatCollapsed ? '▲' : '▼';
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function appendChatMsg(msg) {
  const el = document.getElementById('chat-messages');
  const user = getCurrentUser();
  const isMe = user && (msg.userId === user.id || msg.user_id === user.id);
  const div = document.createElement('div');
  div.className = 'chat-msg';
  const ts = new Date(msg.ts || msg.created_at).toLocaleTimeString('tr-TR',{hour:'2-digit',minute:'2-digit'});
  div.innerHTML = `<span class="chat-user${isMe?' me':''}">${escapeHtml(msg.username)}</span>`+
    `<span class="chat-text">${escapeHtml(msg.text||msg.message)}</span>`+
    `<span class="chat-ts"> ${ts}</span>`;
  el.appendChild(div);
}

function initChat() {
  const token = getToken();
  if (!token || typeof io === 'undefined') return;
  socket = io();
  socket.on('connect', () => socket.emit('chat:join', { token }));
  socket.on('chat:history', msgs => {
    const el = document.getElementById('chat-messages');
    el.innerHTML = '';
    msgs.forEach(appendChatMsg);
    el.scrollTop = el.scrollHeight;
  });
  socket.on('chat:message', msg => {
    appendChatMsg(msg);
    const el = document.getElementById('chat-messages');
    el.scrollTop = el.scrollHeight;
  });
  socket.on('chat:online', count => {
    document.getElementById('chat-online').textContent = count + ' çevrimiçi';
  });
}

function sendChatMsg() {
  if (!socket) return;
  const input = document.getElementById('chat-input');
  const text = input.value.trim();
  if (!text) return;
  socket.emit('chat:message', { text });
  input.value = '';
}

document.addEventListener('DOMContentLoaded', init);
</script>
</body>
</html>"""

game_html = game_html.replace('SVG_PLACEHOLDER', svg_patched)
game_html = game_html.replace('CITIES_PLACEHOLDER', cities_js)

os.makedirs(os.path.join(ROOT, 'public'), exist_ok=True)
out = os.path.join(ROOT, 'public', 'game.html')
with open(out, 'w', encoding='utf-8') as f:
    f.write(game_html)
print(f"\npublic/game.html written: {os.path.getsize(out)//1024} KB")
