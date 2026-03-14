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
    'Marmara':            {'sanayi':1,'tekstil':1,'celik':1},
    'Ege':                {'tekstil':2,'turunçgil':1,'zeytinyagi':2,'uzum':2,'mermer':1},
    'Akdeniz':            {'turunçgil':2,'pamuk':2},
    'Karadeniz':          {'findik':2,'bugday':1,'cay':2,'misir':1,'komur':1},
    'İç Anadolu':         {'bugday':3,'pancar':2,'tuz':1,'elma':1},
    'Doğu Anadolu':       {'bal':2,'kayisi':1},
    'Güneydoğu Anadolu':  {'petrol':1,'fistak':2},
}
REGION_DEM = {
    'Marmara':            {'bugday':2,'findik':2,'turunçgil':1,'petrol':1,'cay':2,'bal':1,'fistak':1},
    'Ege':                {'bugday':1,'sanayi':1,'petrol':2,'komur':1,'celik':1},
    'Akdeniz':            {'bugday':2,'sanayi':1,'tekstil':1,'misir':1,'bal':1},
    'Karadeniz':          {'sanayi':2,'tekstil':1,'pamuk':1,'mermer':1},
    'İç Anadolu':         {'sanayi':1,'tekstil':1,'turunçgil':1,'cay':1,'zeytinyagi':1,'fistak':1},
    'Doğu Anadolu':       {'bugday':2,'tekstil':3,'sanayi':2,'cay':1,'pamuk':1},
    'Güneydoğu Anadolu':  {'bugday':2,'tekstil':2,'sanayi':2,'elma':1,'misir':1},
}
CITY_OVERRIDES = {
    'istanbul':    {'prod':{'sanayi':3,'tekstil':2},             'dem':{'bugday':3,'findik':3,'turunçgil':2,'cay':3,'bal':2,'fistak':2}},
    'kocaeli':     {'prod':{'sanayi':3,'celik':2},               'dem':{'bugday':2,'petrol':2}},
    'sakarya':     {'prod':{'tekstil':1},                        'dem':{}},
    'bursa':       {'prod':{'tekstil':2,'celik':1},              'dem':{'sanayi':1,'bugday':1}},
    'ankara':      {'prod':{'bugday':2,'sanayi':1},              'dem':{'sanayi':3,'tekstil':2,'turunçgil':2,'cay':2,'zeytinyagi':1}},
    'izmir':       {'prod':{'tekstil':2,'turunçgil':1,'zeytinyagi':2,'uzum':1}, 'dem':{'sanayi':2,'petrol':3,'findik':2}},
    'denizli':     {'prod':{'tekstil':3,'pamuk':1},              'dem':{}},
    'manisa':      {'prod':{'tekstil':1,'turunçgil':1,'uzum':2}, 'dem':{}},
    'aydin':       {'prod':{'turunçgil':1,'tekstil':1,'zeytinyagi':1,'uzum':1}, 'dem':{}},
    'mugla':       {'prod':{'turunçgil':1,'mermer':2},           'dem':{'sanayi':1}},
    'bilecik':     {'prod':{'mermer':1,'tekstil':1},             'dem':{}},
    'antalya':     {'prod':{'turunçgil':3},                      'dem':{'sanayi':2,'tekstil':2,'bugday':2}},
    'mersin':      {'prod':{'turunçgil':2,'bugday':1},           'dem':{'sanayi':2}},
    'adana':       {'prod':{'turunçgil':2,'bugday':2,'pamuk':2}, 'dem':{'sanayi':2}},
    'hatay':       {'prod':{'turunçgil':2,'zeytinyagi':1},       'dem':{'sanayi':1}},
    'giresun':     {'prod':{'findik':3},                         'dem':{'sanayi':2}},
    'ordu':        {'prod':{'findik':3,'misir':2},               'dem':{'sanayi':1}},
    'trabzon':     {'prod':{'findik':2,'misir':1},               'dem':{'sanayi':2,'tekstil':1}},
    'rize':        {'prod':{'cay':3,'findik':0},                 'dem':{'sanayi':2,'bugday':1}},
    'artvin':      {'prod':{'cay':1,'bal':1},                    'dem':{'sanayi':1}},
    'samsun':      {'prod':{'findik':1,'bugday':1,'misir':2},    'dem':{'sanayi':2,'tekstil':1}},
    'zonguldak':   {'prod':{'komur':3},                          'dem':{'bugday':2,'sanayi':1}},
    'kastamonu':   {'prod':{'komur':1,'bal':1},                  'dem':{'sanayi':1}},
    'konya':       {'prod':{'bugday':3,'pancar':2,'tuz':1},      'dem':{'sanayi':2,'tekstil':2,'findik':2,'turunçgil':2}},
    'eskisehir':   {'prod':{'bugday':2,'tekstil':1},             'dem':{'sanayi':2}},
    'kayseri':     {'prod':{'bugday':1,'tekstil':1},             'dem':{'sanayi':2}},
    'sivas':       {'prod':{'bugday':2},                         'dem':{'sanayi':2,'tekstil':1}},
    'afyon':       {'prod':{'pancar':1,'elma':1},                'dem':{'sanayi':1}},
    'isparta':     {'prod':{'elma':2},                           'dem':{'sanayi':1,'tekstil':1}},
    'nigde':       {'prod':{'elma':1,'tuz':1},                   'dem':{'sanayi':1}},
    'malatya':     {'prod':{'kayisi':3},                         'dem':{'sanayi':2,'tekstil':1}},
    'elazig':      {'prod':{'kayisi':1},                         'dem':{'sanayi':1,'tekstil':1}},
    'batman':      {'prod':{'petrol':3},                         'dem':{'bugday':2,'sanayi':2}},
    'diyarbakir':  {'prod':{'petrol':2},                         'dem':{'bugday':2,'tekstil':2}},
    'adiyaman':    {'prod':{'petrol':2},                         'dem':{'bugday':2,'tekstil':1}},
    'siirt':       {'prod':{'petrol':1},                         'dem':{'bugday':2,'tekstil':2}},
    'sirnak':      {'prod':{'petrol':1},                         'dem':{'bugday':2,'tekstil':2}},
    'sanliurfa':   {'prod':{'pamuk':1},                          'dem':{'bugday':2,'tekstil':2,'sanayi':2,'petrol':1}},
    'gaziantep':   {'prod':{'tekstil':1,'fistak':2},             'dem':{'bugday':2,'sanayi':2,'petrol':1}},
    'mardin':      {'prod':{},                                   'dem':{'bugday':2,'tekstil':2,'sanayi':2}},
    'erzurum':     {'prod':{'bugday':1},                         'dem':{'bugday':1,'tekstil':3,'sanayi':3}},
    'van':         {'prod':{'bal':1},                            'dem':{'bugday':2,'tekstil':3,'sanayi':2}},
    'kars':        {'prod':{'bugday':1,'bal':1},                 'dem':{'tekstil':2,'sanayi':2}},
    'agri':        {'prod':{},                                   'dem':{'bugday':2,'tekstil':2,'sanayi':2}},
    'hakkari':     {'prod':{},                                   'dem':{'bugday':2,'tekstil':3,'sanayi':3}},
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
.price-row{margin-bottom:6px;padding:8px;background:#1a1a2e;border-radius:6px}
.price-row-top{display:flex;align-items:center;gap:8px}
.price-icon{font-size:16px;width:22px;text-align:center;flex-shrink:0}
.price-info{flex:1;min-width:0}
.price-name{font-size:11px;color:#aaa;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.price-val{font-size:13px;font-weight:700;color:#4ecca3}
.price-trend{font-size:10px}
.price-trend.up{color:#e94560}
.price-trend.down{color:#4ecca3}
.price-actions{display:flex;flex-direction:column;gap:3px;margin-top:5px}
.qty-group{display:flex;gap:2px}
.qty-btn-sm{background:#0f3460;border:1px solid;padding:4px 0;border-radius:3px;cursor:pointer;font-size:10px;font-weight:700;transition:all .15s;flex:1;text-align:center}
.qty-btn-buy{border-color:#4ecca3;color:#4ecca3}
.qty-btn-buy:hover:not(:disabled){background:#4ecca3;color:#16213e}
.qty-btn-sell{border-color:#e94560;color:#e94560}
.qty-btn-sell:hover:not(:disabled){background:#e94560;color:#fff}
.qty-btn-sm:disabled{opacity:.3;cursor:not-allowed}
/* Energy bar */
.energy-bar-wrap{width:54px;height:4px;background:#0f3460;border-radius:2px;margin-top:3px}
.energy-fill{height:100%;background:#f5a623;border-radius:2px;transition:width .4s}
.energy-fill.low{background:#e94560}
#panel-travel{border-top:1px solid #0f3460;padding-top:12px;margin-top:4px}
#btn-travel{width:100%;padding:12px;background:#e94560;border:none;color:#fff;font-size:14px;font-weight:700;border-radius:6px;cursor:pointer;transition:all .2s;letter-spacing:1px}
#btn-travel:hover{background:#c73652}
#btn-travel:disabled{background:#555;cursor:not-allowed}
#travel-time-display{text-align:center;font-size:12px;color:#888;margin-top:6px}
#travel-status{text-align:center;padding:20px;color:#888;font-style:italic}
/* City governance */
.gov-banner{padding:8px 10px;border-radius:6px;margin-bottom:10px;font-size:12px;display:flex;align-items:center;justify-content:space-between;gap:8px}
.gov-banner.owned{background:#0f3460;border:1px solid #4ecca3}
.gov-banner.unclaimed{background:#1a1a2e;border:1px dashed #555}
.gov-banner.auction{background:#2d1a1a;border:1px solid #e94560}
.gov-owner{font-weight:700;color:#4ecca3}
.gov-unclaimed{color:#555}
.gov-tax{font-size:11px;color:#f5a623;background:#16213e;padding:2px 6px;border-radius:4px}
.happiness-bar{height:6px;border-radius:3px;background:#0f3460;overflow:hidden;margin-top:4px}
.happiness-fill{height:100%;border-radius:3px;transition:width .4s}
.gov-section{border-top:1px solid #0f3460;padding-top:12px;margin-top:10px}
.gov-section h4{font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px}
.gov-btn{width:100%;padding:8px;border-radius:4px;cursor:pointer;font-size:12px;border:1px solid;background:#0f3460;transition:all .2s;margin-bottom:5px;text-align:left}
.gov-btn.green{border-color:#4ecca3;color:#4ecca3}
.gov-btn.green:hover:not(:disabled){background:#4ecca3;color:#16213e}
.gov-btn.red{border-color:#e94560;color:#e94560}
.gov-btn.red:hover:not(:disabled){background:#e94560;color:#fff}
.gov-btn.yellow{border-color:#f5a623;color:#f5a623}
.gov-btn.yellow:hover:not(:disabled){background:#f5a623;color:#16213e}
.gov-btn:disabled{opacity:.3;cursor:not-allowed}
.infra-grid{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-bottom:8px}
.infra-item{background:#1a1a2e;border-radius:4px;padding:6px 8px;font-size:11px}
.infra-item .infra-name{color:#888}
.infra-item .infra-lvl{color:#4ecca3;font-weight:700}
.tax-slider{width:100%;margin:6px 0;accent-color:#f5a623}
.auction-box{background:#2d1a1a;border:1px solid #e94560;border-radius:6px;padding:10px;margin-bottom:8px}
.auction-box .auction-title{font-size:12px;color:#e94560;font-weight:700;margin-bottom:6px}
.auction-box .auction-detail{font-size:11px;color:#aaa;margin-bottom:4px}
.auction-box .auction-bid{font-size:13px;color:#f5a623;font-weight:700}
/* Owned city map rings */
.city-ring{pointer-events:none}

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
  <div class="stat"><label>Araç</label><span id="hud-capacity">🚐 0/20 ton</span></div>
  <div class="sep"></div>
  <div class="stat">
    <label>Yakıt ⚡</label>
    <span id="hud-energy-val" style="font-size:12px">100</span>
    <div class="energy-bar-wrap"><div id="hud-energy-bar" class="energy-fill" style="width:100%"></div></div>
  </div>
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
      <div id="gov-banner"></div>
      <div id="travel-status"></div>
      <div id="panel-prices">
        <h3>Pazar Fiyatları</h3>
        <div id="price-list"></div>
      </div>
      <div id="panel-travel">
        <button id="btn-travel" onclick="travelToSelected()">▶ Yola Çık</button>
        <div id="travel-time-display"></div>
      </div>
      <div id="panel-garage" style="display:none;border-top:1px solid #0f3460;padding-top:12px;margin-top:12px">
        <h3 style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px">🔧 Garaj</h3>
        <div id="garage-content"></div>
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
  bugday:     {name:'Buğday',        icon:'🌾', basePrice:800,   unit:'ton'},
  findik:     {name:'Fındık',        icon:'🌰', basePrice:4500,  unit:'ton'},
  turunçgil:  {name:'Turunçgil',     icon:'🍊', basePrice:1200,  unit:'ton'},
  tekstil:    {name:'Tekstil',       icon:'👔', basePrice:2800,  unit:'ton'},
  sanayi:     {name:'Sanayi Par.',   icon:'⚙️',  basePrice:6000,  unit:'ton'},
  petrol:     {name:'Ham Petrol',    icon:'🛢️',  basePrice:3500,  unit:'ton'},
  cay:        {name:'Çay',           icon:'🍵', basePrice:2000,  unit:'ton'},
  zeytinyagi: {name:'Zeytinyağı',    icon:'🫒', basePrice:8000,  unit:'ton'},
  kayisi:     {name:'Kayısı',        icon:'🍑', basePrice:3500,  unit:'ton'},
  pamuk:      {name:'Pamuk',         icon:'🌿', basePrice:2200,  unit:'ton'},
  fistak:     {name:'Antep Fıstığı', icon:'🥜', basePrice:12000, unit:'ton'},
  elma:       {name:'Elma',          icon:'🍎', basePrice:900,   unit:'ton'},
  tuz:        {name:'Tuz',           icon:'🧂', basePrice:400,   unit:'ton'},
  komur:      {name:'Kömür',         icon:'🪨', basePrice:1500,  unit:'ton'},
  mermer:     {name:'Mermer',        icon:'🏛️', basePrice:2500,  unit:'ton'},
  uzum:       {name:'Kuru Üzüm',     icon:'🍇', basePrice:1800,  unit:'ton'},
  bal:        {name:'Bal',           icon:'🍯', basePrice:15000, unit:'ton'},
  misir:      {name:'Mısır',         icon:'🌽', basePrice:600,   unit:'ton'},
  celik:      {name:'Demir/Çelik',   icon:'🔩', basePrice:4500,  unit:'ton'},
  pancar:     {name:'Şeker Pancarı', icon:'🌱', basePrice:700,   unit:'ton'}
};
const PRODUCT_IDS = Object.keys(PRODUCTS);

const TRUCK_TIERS = [
  {name:'Kamyonet', cap:20,  cost:0,      icon:'🚐'},
  {name:'Kamyon',   cap:50,  cost:150000, icon:'🚛'},
  {name:'TIR',      cap:100, cost:500000, icon:'🚚'},
];
const MAX_ENERGY  = 100;
const ENERGY_COST = 30;  // max fuel per max-distance trip

// ============================================================
// CITY GOVERNANCE (server-synced)
// ============================================================
let cityGov = {};  // cityId → {ownership, stats, auction, baseValue}

async function loadCityGov() {
  try {
    const res = await fetch('/api/cities', { headers: authHeader() });
    if (!res.ok) return;
    const rows = await res.json();
    rows.forEach(r => {
      if (!cityGov[r.city_id]) cityGov[r.city_id] = {};
      Object.assign(cityGov[r.city_id], r);
    });
  } catch (e) { console.warn('loadCityGov failed', e); }
}

async function loadCityDetail(cityId) {
  try {
    const res = await fetch(`/api/cities/${cityId}`, { headers: authHeader() });
    if (!res.ok) return;
    const data = await res.json();
    cityGov[cityId] = data;
    return data;
  } catch (e) { return null; }
}

function authHeader() {
  return { 'Authorization': 'Bearer ' + getToken(), 'Content-Type': 'application/json' };
}

async function apiPost(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: authHeader(),
    body: JSON.stringify(body),
  });
  return res.json();
}

// ── Governance actions ──────────────────────────────────────
async function claimCity(cityId) {
  const data = await apiPost(`/api/cities/${cityId}/claim`, {});
  if (data.error) return showToast(data.error, 'error');
  state.money = data.newMoney;
  updateHUD();
  showToast(`🏛️ ${CITIES[cityId]?.name} satın alındı! -${data.cost.toLocaleString('tr-TR')} TL`);
  await loadCityDetail(cityId);
  refreshCityPanel();
}

async function setTaxRate(cityId, rate) {
  const data = await apiPost(`/api/cities/${cityId}/tax`, { rate });
  if (data.error) return showToast(data.error, 'error');
  if (cityGov[cityId]?.stats) cityGov[cityId].stats.tax_rate = rate;
  showToast(`Vergi oranı %${rate} olarak ayarlandı`);
  refreshCityPanel();
}

async function investInfra(cityId, type) {
  const data = await apiPost(`/api/cities/${cityId}/invest`, { type });
  if (data.error) return showToast(data.error, 'error');
  showToast(`✅ Yatırım yapıldı! -${data.cost.toLocaleString('tr-TR')} TL (hazineden)`);
  await loadCityDetail(cityId);
  refreshCityPanel();
}

async function collectTreasury(cityId) {
  const data = await apiPost(`/api/cities/${cityId}/collect`, {});
  if (data.error) return showToast(data.error, 'error');
  state.money = data.newMoney;
  updateHUD();
  showToast(`💰 +${data.payout.toLocaleString('tr-TR')} TL vergi geliri alındı!`);
  await loadCityDetail(cityId);
  refreshCityPanel();
}

async function startAuction(cityId) {
  const data = await apiPost(`/api/cities/${cityId}/auction/start`, {});
  if (data.error) return showToast(data.error, 'error');
  const msg = data.triggerCost > 0
    ? `⚔️ Müzayede başlatıldı! -${data.triggerCost.toLocaleString('tr-TR')} TL`
    : `⚔️ Halk isyanıyla müzayede başlatıldı!`;
  showToast(msg);
  await loadCityDetail(cityId);
  refreshCityPanel();
}

async function placeBid(cityId) {
  const input = document.getElementById('bid-input');
  const amount = parseInt(input?.value) || 0;
  if (!amount) return showToast('Teklif miktarı giriniz', 'error');
  const data = await apiPost(`/api/cities/${cityId}/auction/bid`, { amount });
  if (data.error) return showToast(data.error, 'error');
  showToast(`Teklif verildi: ${amount.toLocaleString('tr-TR')} TL`);
  await loadCityDetail(cityId);
  refreshCityPanel();
}

async function resolveAuction(cityId) {
  const data = await apiPost(`/api/cities/${cityId}/auction/resolve`, {});
  if (data.error) return showToast(data.error, 'error');
  if (data.result === 'transferred')
    showToast(`🏆 ${data.winner} şehri kazandı! ${data.amount.toLocaleString('tr-TR')} TL`);
  else
    showToast('Teklif gelmedi, başkan devam ediyor');
  await loadCityDetail(cityId);
  await loadCityGov();
  refreshCityPanel();
  updateMarkers();
}

async function payTax(cityId, taxAmount) {
  if (taxAmount <= 0) return;
  fetch(`/api/cities/${cityId}/tax-payment`, {
    method: 'POST',
    headers: authHeader(),
    body: JSON.stringify({ amount: taxAmount }),
  }).catch(() => {});
}

// ============================================================
// CITIES (auto-generated from SVG)
// ============================================================
CITIES_PLACEHOLDER

// ============================================================
// NPC DEFINITIONS
// ============================================================
const NPC_DEFS = [
  {id:'npc1',name:'Karadeniz Tüccarı',  route:['giresun','istanbul'],   product:'findik',     amount:8},
  {id:'npc2',name:'Akdeniz Tüccarı',    route:['antalya','ankara'],     product:'turunçgil',  amount:6},
  {id:'npc3',name:'Ege Tüccarı',        route:['denizli','kocaeli'],    product:'tekstil',    amount:7},
  {id:'npc4',name:'Sanayi Tüccarı',     route:['kocaeli','erzurum'],    product:'sanayi',     amount:5},
  {id:'npc5',name:'Güney Tüccarı',      route:['batman','izmir'],       product:'petrol',     amount:6},
  {id:'npc6',name:'Çay Tüccarı',        route:['rize','istanbul'],      product:'cay',        amount:5},
  {id:'npc7',name:'Kayısı Tüccarı',     route:['malatya','istanbul'],   product:'kayisi',     amount:6},
  {id:'npc8',name:'Ege Yağ Tüccarı',    route:['izmir','ankara'],       product:'zeytinyagi', amount:4},
  {id:'npc9',name:'Fıstık Tüccarı',     route:['gaziantep','istanbul'], product:'fistak',     amount:3},
];

// ============================================================
// NEWS EVENTS
// ============================================================
const NEWS_EVENTS = [
  {text:'Karadeniz bölgesinde fındık rekoltesi rekor kırdı!',              city:'giresun',   prod:'findik',     delta:-0.2},
  {text:'İstanbul limanında grev başladı, tekstil ithalatı durdu!',        city:'istanbul',  prod:'tekstil',    delta:0.25},
  {text:'Akdeniz\'de kuraklık, turunçgil hasatı düştü.',                   city:'antalya',   prod:'turunçgil',  delta:0.2},
  {text:'Kocaeli\'de fabrika yangını: sanayi parçası üretimi aksadı.',     city:'kocaeli',   prod:'sanayi',     delta:0.3},
  {text:'Güneydoğu\'da boru hattı onarımı tamamlandı, petrol akışı arttı.',city:'batman',   prod:'petrol',     delta:-0.15},
  {text:'Konya\'da buğday mahsulü beklentilerin üzerinde çıktı.',          city:'konya',     prod:'bugday',     delta:-0.2},
  {text:'Erzurum\'da şiddetli kış: tekstil talebi patladı!',               city:'erzurum',   prod:'tekstil',    delta:0.2},
  {text:'Ankara\'da inşaat hız kazandı, sanayi talebi arttı.',             city:'ankara',    prod:'sanayi',     delta:0.2},
  {text:'Gaziantep tekstil fuarı büyük ilgi gördü.',                       city:'gaziantep', prod:'tekstil',    delta:0.1},
  {text:'Van Gölü\'nde turizm patladı, gıda talebi arttı.',                city:'van',       prod:'bugday',     delta:0.15},
  {text:'Rize\'de çay rekoltesi mükemmel; ihracat kapıları açıldı.',       city:'rize',      prod:'cay',        delta:-0.2},
  {text:'Malatya\'da kayısı hasatı beklentinin üzerinde!',                 city:'malatya',   prod:'kayisi',     delta:-0.25},
  {text:'Zonguldak maden ocaklarında grev: kömür fiyatları fırladı.',      city:'zonguldak', prod:'komur',      delta:0.3},
  {text:'Ege zeytinliklerinde don felaketi: zeytinyağı fiyatları arttı.',  city:'izmir',     prod:'zeytinyagi', delta:0.25},
  {text:'Gaziantep\'te fıstık hasatında verim düşüklüğü yaşandı.',         city:'gaziantep', prod:'fistak',     delta:0.2},
  {text:'Doğu Anadolu\'da arıcılık gelişiyor, bal üretimi patladı.',       city:'van',       prod:'bal',        delta:-0.2},
  {text:'Ege bağbozumu erken ve bereketli: kuru üzüm ihracatı arttı.',     city:'manisa',    prod:'uzum',       delta:-0.2},
  {text:'Mısır hasatı sele uğradı, Samsun\'da fiyatlar yükseldi.',         city:'samsun',    prod:'misir',      delta:0.25},
  {text:'Konya şeker fabrikası kapasitesini artırdı.',                      city:'konya',     prod:'pancar',     delta:-0.15},
  {text:'Kocaeli\'de demir-çelik ihracatı rekor kırdı!',                   city:'kocaeli',   prod:'celik',      delta:-0.2},
  {text:'İsparta\'da elma rekoltesi beklentileri aştı, fiyatlar düştü.',   city:'isparta',   prod:'elma',       delta:-0.2},
  {text:'Tuz Gölü çevresinde yoğun hasat: tuz fiyatları geriledi.',        city:'konya',     prod:'tuz',        delta:-0.15},
  {text:'Muğla mermer ocaklarında kapasite artırımına gidildi.',           city:'mugla',     prod:'mermer',     delta:-0.15},
  {text:'Artvin\'de çiçek mevsimi: bal üretimi zirveye ulaştı.',           city:'artvin',    prod:'bal',        delta:-0.2},
  {text:'Adana\'da pamuk tarlalarına zararlı böcek musallat oldu!',        city:'adana',     prod:'pamuk',      delta:0.3},
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
  money:          50000,
  position:       'ankara',
  inventory:      {},
  truckCapacity:  20,
  truckTier:      0,
  energy:         MAX_ENERGY,
  traveling:      null,
  selectedCity:   null,
  lastEcoTick:    0,
  lastNewsTime:   0,
  lastEnergyTick: 0,
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

function energyCost(from, to) {
  return Math.max(5, Math.ceil(cityDist(from, to) / MAX_DIST * ENERGY_COST));
}

function startTravel(target) {
  if (state.traveling) return;
  if (state.position === target) { showToast('Zaten buradasınız!'); return; }
  const needed = energyCost(state.position, target);
  if (state.energy < needed) {
    showToast(`Yetersiz yakıt! Gereken: ${needed} ⚡`, 'error');
    return;
  }
  const dur = travelDuration(state.position, target);
  state.energy = Math.max(0, state.energy - needed);
  state.traveling = {from:state.position, to:target, startTime:Date.now(), duration:dur};
  state.selectedCity = null;
  closeCityPanel();
  updateHUD();
  showToast(`${CITIES[target]?.name||target}'e yola çıkıldı (${Math.round(dur/1000)}s) ⚡-${needed}`);
}

function travelToSelected() {
  if (state.selectedCity) startTravel(state.selectedCity);
}

// ============================================================
// BUY / SELL
// ============================================================
function cityTaxRate(cityId) {
  return cityGov[cityId]?.stats?.tax_rate ?? cityGov[cityId]?.tax_rate ?? 0;
}

function buyProduct(pid, qty) {
  qty = parseInt(qty)||0;
  if (qty <= 0) return;
  const price = cachedPrices[state.position]?.[pid];
  if (!price) return;
  const tax     = cityTaxRate(state.position);
  const baseCost = price * qty;
  const taxCost  = Math.round(baseCost * tax / 100);
  const cost     = baseCost + taxCost;
  if (cost > state.money) return showToast('Yeterli para yok!','error');
  if (invLoad() + qty > state.truckCapacity) return showToast('Araç kapasitesi dolu!','error');
  state.money -= cost;
  state.inventory[pid] = (state.inventory[pid]||0) + qty;
  citySupply[state.position][pid] = Math.max(1, (citySupply[state.position][pid]||5) - qty*0.4);
  refreshCityPanel();
  updateHUD();
  updateInventoryBar();
  const taxStr = taxCost > 0 ? ` (+${taxCost.toLocaleString('tr-TR')} TL vergi)` : '';
  showToast(`${qty} ton ${PRODUCTS[pid].name} → ${cost.toLocaleString('tr-TR')} TL${taxStr}`);
  logTransaction('buy', pid, qty, price);
  if (taxCost > 0) payTax(state.position, taxCost);
}

function sellProduct(pid, qty) {
  qty = parseInt(qty)||0;
  const have = state.inventory[pid]||0;
  if (qty <= 0 || have <= 0) return;
  qty = Math.min(qty, have);
  const price = cachedPrices[state.position]?.[pid];
  if (!price) return;
  const tax     = cityTaxRate(state.position);
  const baseEarn = price * qty;
  const taxCost  = Math.round(baseEarn * tax / 100);
  const earn     = baseEarn - taxCost;
  state.money += earn;
  state.inventory[pid] = have - qty;
  if (!state.inventory[pid]) delete state.inventory[pid];
  citySupply[state.position][pid] = Math.min(13, (citySupply[state.position][pid]||5) + qty*0.4);
  refreshCityPanel();
  updateHUD();
  updateInventoryBar();
  const taxStr = taxCost > 0 ? ` (-${taxCost.toLocaleString('tr-TR')} TL vergi)` : '';
  showToast(`Satıldı! +${earn.toLocaleString('tr-TR')} TL${taxStr}`);
  logTransaction('sell', pid, qty, price);
  if (taxCost > 0) payTax(state.position, taxCost);
}

function buyMaxProduct(pid) {
  const avail = state.truckCapacity - invLoad();
  if (avail <= 0) return showToast('Araç kapasitesi dolu!','error');
  buyProduct(pid, avail);
}

function sellAllProduct(pid) {
  const have = state.inventory[pid]||0;
  if (have <= 0) return;
  sellProduct(pid, have);
}

function upgradeTruck(tier) {
  if (state.truckTier >= tier) return;
  const t = TRUCK_TIERS[tier];
  if (state.money < t.cost) return showToast('Yeterli para yok!','error');
  state.money -= t.cost;
  state.truckTier = tier;
  state.truckCapacity = t.cap;
  updateHUD();
  updateInventoryBar();
  refreshCityPanel();
  showToast(`${t.icon} ${t.name} satın alındı! Kapasite: ${t.cap} ton`);
  saveGame();
}

function refuelVehicle() {
  const needed = MAX_ENERGY - state.energy;
  if (needed < 1) return showToast('Yakıt zaten dolu!');
  const cost = Math.ceil(needed * 15);
  if (state.money < cost) return showToast(`Yeterli para yok! Gereken: ${cost.toLocaleString('tr-TR')} TL`,'error');
  state.money -= cost;
  state.energy = MAX_ENERGY;
  updateHUD();
  refreshCityPanel();
  showToast(`Araç yakıtlandı! -${cost.toLocaleString('tr-TR')} TL`);
}

// ============================================================
// GOVERNANCE PANEL RENDERER
// ============================================================
function renderGovPanel(cid) {
  const banner  = document.getElementById('gov-banner');
  if (!banner) return;

  const gov     = cityGov[cid];
  const user    = getCurrentUser();
  const isOwner = gov?.owner_id && user && gov.owner_id === user.id;
  const owned   = !!gov?.owner_id;
  const tax     = gov?.stats?.tax_rate ?? gov?.tax_rate ?? 0;
  const treasury= gov?.stats?.treasury ?? 0;
  const happiness = gov?.stats?.happiness ?? null;
  const auction = gov?.auction;
  const prot    = gov?.protected_until && new Date(gov.protected_until) > new Date();

  // ── Ownership badge ──────────────────────────────────────
  if (!owned) {
    const bv = gov?.baseValue || 40000;
    const canBuy = state.money >= bv;
    banner.className = 'gov-banner unclaimed';
    banner.innerHTML = `
      <div>
        <div class="gov-unclaimed">🏚️ Sahipsiz şehir</div>
        <div style="font-size:11px;color:#888;margin-top:2px">Satın alma bedeli: <b style="color:#fff">${bv.toLocaleString('tr-TR')} TL</b></div>
      </div>
      <button class="gov-btn green" style="width:auto;padding:6px 12px;margin:0" onclick="claimCity('${cid}')" ${canBuy?'':'disabled'}>Satın Al</button>`;
  } else {
    const happyColor = happiness === null ? '#888' : happiness >= 60 ? '#4ecca3' : happiness >= 30 ? '#f5a623' : '#e94560';
    const happyPct   = happiness ?? 70;
    banner.className = 'gov-banner owned';
    banner.innerHTML = `
      <div style="flex:1">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
          <span>🏛️</span>
          <span class="gov-owner">${escapeHtml(gov.owner_name)}</span>
          <span class="gov-tax">%${tax} vergi</span>
          ${prot ? '<span style="font-size:10px;color:#888">🛡️ Koruma</span>' : ''}
        </div>
        <div style="font-size:10px;color:#888;margin-bottom:3px">Halk mutluluğu: <span style="color:${happyColor}">${happyPct}/100</span></div>
        <div class="happiness-bar"><div class="happiness-fill" style="width:${happyPct}%;background:${happyColor}"></div></div>
      </div>`;
  }

  // Load full detail if not yet loaded
  if (owned && !gov?.stats) {
    loadCityDetail(cid).then(() => refreshCityPanel());
  }

  // ── Existing auction box ─────────────────────────────────
  const existingAuct = document.getElementById('gov-auction-box');
  if (existingAuct) existingAuct.remove();

  if (auction) {
    const remaining = Math.max(0, Math.ceil((new Date(auction.ends_at) - new Date()) / 60000));
    const canResolve = new Date(auction.ends_at) <= new Date();
    const box = document.createElement('div');
    box.id = 'gov-auction-box';
    box.className = 'auction-box';
    box.innerHTML = `
      <div class="auction-title">⚔️ Devrilme Müzayedesi</div>
      <div class="auction-detail">Bitiş: ${canResolve ? '<span style="color:#e94560">Bitti!</span>' : remaining + ' dakika kaldı'}</div>
      <div class="auction-bid">Lider: ${auction.top_bidder_name ? escapeHtml(auction.top_bidder_name) + ' — ' + auction.top_bid.toLocaleString('tr-TR') + ' TL' : 'Henüz teklif yok'}</div>
      ${canResolve
        ? `<button class="gov-btn red" style="margin-top:8px" onclick="resolveAuction('${cid}')">Müzayedeyi Sonuçlandır</button>`
        : !isOwner
          ? `<div style="display:flex;gap:4px;margin-top:8px">
               <input id="bid-input" type="number" min="${auction.top_bid+1}" placeholder="Teklif (TL)"
                 style="flex:1;background:#0d1117;border:1px solid #e94560;color:#fff;padding:6px;border-radius:4px;font-size:12px"/>
               <button class="gov-btn red" style="width:auto;padding:6px 10px" onclick="placeBid('${cid}')">Teklif Ver</button>
             </div>`
          : '<div style="font-size:11px;color:#888;margin-top:6px">Kendi şehrinize teklif veremezsiniz.</div>'
      }`;
    banner.insertAdjacentElement('afterend', box);
  }

  // ── Mayor panel (only for owner) ─────────────────────────
  const existingPanel = document.getElementById('gov-mayor-panel');
  if (existingPanel) existingPanel.remove();

  if (isOwner && gov?.stats) {
    const stats  = gov.stats;
    const infras = [
      {key:'storage', name:'📦 Depo',    bonus:'+100t kapasite'},
      {key:'road',    name:'🛣️ Yol',     bonus:'-10% seyahat süresi'},
      {key:'market',  name:'🏪 Pazar',   bonus:'+5 ilan kapasitesi'},
      {key:'factory', name:'🏭 Fabrika', bonus:'+20% yerel üretim'},
    ];
    const infraCosts = {
      storage:[30000,50000,100000], road:[20000,40000,80000],
      market:[25000,45000,90000],   factory:[40000,70000,130000],
    };
    const infraHtml = infras.map(inf => {
      const lvl  = stats[`infra_${inf.key}`] || 0;
      const next = lvl < 3 ? infraCosts[inf.key][lvl] : null;
      const canInvest = next !== null && treasury >= next;
      return `<div class="infra-item">
        <div class="infra-name">${inf.name}</div>
        <div class="infra-lvl">${'★'.repeat(lvl)}${'☆'.repeat(3-lvl)}</div>
        ${next !== null
          ? `<button class="gov-btn green" style="margin:4px 0 0;padding:3px 6px;font-size:10px;width:100%"
               onclick="investInfra('${cid}','${inf.key}')" ${canInvest?'':'disabled'}>
               Yükselt ${next.toLocaleString('tr-TR')} TL</button>`
          : '<div style="font-size:10px;color:#4ecca3;margin-top:2px">Maks</div>'}
      </div>`;
    }).join('');

    const panel = document.createElement('div');
    panel.id = 'gov-mayor-panel';
    panel.className = 'gov-section';
    panel.innerHTML = `
      <h4>⚙️ Başkanlık Paneli</h4>
      <div style="margin-bottom:10px">
        <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px">
          <span style="color:#888">Hazine</span>
          <span style="color:#4ecca3;font-weight:700">${treasury.toLocaleString('tr-TR')} TL</span>
        </div>
        <button class="gov-btn yellow" onclick="collectTreasury('${cid}')" ${treasury>=1000?'':'disabled'}>
          💰 Vergi Geliri Al (%80 = ${Math.round(treasury*0.8).toLocaleString('tr-TR')} TL)</button>
      </div>
      <div style="margin-bottom:10px">
        <div style="font-size:11px;color:#888;margin-bottom:4px">Vergi Oranı: <b id="tax-display" style="color:#f5a623">%${tax}</b></div>
        <input type="range" class="tax-slider" min="0" max="15" value="${tax}"
          oninput="document.getElementById('tax-display').textContent='%'+this.value"
          onchange="setTaxRate('${cid}',parseInt(this.value))"/>
        <div style="display:flex;justify-content:space-between;font-size:10px;color:#555">
          <span>%0 özgür</span><span>%5 standart</span><span>%15 max</span>
        </div>
      </div>
      <div>
        <div style="font-size:11px;color:#888;margin-bottom:6px">Altyapı</div>
        <div class="infra-grid">${infraHtml}</div>
      </div>`;
    document.getElementById('panel-garage').insertAdjacentElement('beforebegin', panel);
  }

  // ── Overthrow button (not owner, city owned, no active auction) ──
  const existingOvr = document.getElementById('gov-overthrow');
  if (existingOvr) existingOvr.remove();

  if (owned && !isOwner && !auction) {
    const happiness = gov?.stats?.happiness ?? 70;
    const bv = gov?.baseValue || 40000;
    const challengeCost = happiness < 25 ? 0 : Math.round(bv * 0.15);
    const canChallenge = state.money >= challengeCost;
    const ovrDiv = document.createElement('div');
    ovrDiv.id = 'gov-overthrow';
    ovrDiv.className = 'gov-section';
    ovrDiv.innerHTML = `
      <button class="gov-btn red" onclick="startAuction('${cid}')" ${canChallenge?'':'disabled'}>
        ⚔️ Devrilme Başlat ${challengeCost > 0 ? '— ' + challengeCost.toLocaleString('tr-TR') + ' TL' : '(ücretsiz — halk mutsuz)'}
      </button>`;
    document.getElementById('panel-garage').insertAdjacentElement('beforebegin', ovrDiv);
  }
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

  // City ownership rings
  const user = getCurrentUser();
  Object.entries(cityGov).forEach(([cid, gov]) => {
    if (!gov?.owner_id) return;
    const city = CITIES[cid];
    if (!city) return;
    const isMe = user && gov.owner_id === user.id;
    const ring = svgEl('circle');
    ring.setAttribute('cx', city.cx);
    ring.setAttribute('cy', city.cy);
    ring.setAttribute('r', '8');
    ring.setAttribute('fill', 'none');
    ring.setAttribute('stroke', isMe ? '#4ecca3' : '#f5a623');
    ring.setAttribute('stroke-width', '2');
    ring.setAttribute('opacity', '0.7');
    ring.setAttribute('class', 'city-ring');
    markersSvg.appendChild(ring);
  });

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
  // Load fresh governance data for this city
  loadCityDetail(cid).then(data => { if (data) refreshCityPanel(); });
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
    ttDisplay.textContent = '';
  } else if (cid === state.position) {
    travelStatus.textContent = '📍 Şu an buradasınız';
    travelBtn.disabled = true;
    travelBtn.textContent = '▶ Buraya Git';
    ttDisplay.textContent = '';
  } else {
    travelStatus.textContent = '';
    const dur    = Math.round(travelDuration(state.position, cid)/1000);
    const eCost  = energyCost(state.position, cid);
    const hasNrg = state.energy >= eCost;
    travelBtn.disabled = !hasNrg;
    travelBtn.textContent = `▶ ${city.name}'e Git`;
    ttDisplay.textContent  = `⏱ ~${dur}s  ⚡ -${eCost}${!hasNrg ? '  (yakıt yetersiz!)' : ''}`;
    ttDisplay.style.color  = hasNrg ? '#888' : '#e94560';
  }

  // Price list
  const pl = document.getElementById('price-list');
  pl.innerHTML = '';
  PRODUCT_IDS.forEach(pid => {
    const p     = PRODUCTS[pid];
    const price = cachedPrices[cid]?.[pid] || 0;
    const inInv = state.inventory[pid] || 0;
    const atCity = !state.traveling && cid === state.position;
    const dis     = atCity ? '' : 'disabled';
    const disSell = atCity && inInv ? '' : 'disabled';

    const prodLvl = (CITIES[cid].prod||{})[pid]||0;
    const demLvl  = (CITIES[cid].dem||{})[pid]||0;
    let trendHtml = '';
    if (prodLvl >= 2)      trendHtml = `<span class="price-trend down">↓ üretim</span>`;
    else if (demLvl >= 2)  trendHtml = `<span class="price-trend up">↑ talep</span>`;
    const invLabel = inInv ? ` <span style="color:#4ecca3;font-size:10px">✓${inInv}t</span>` : '';

    const row = document.createElement('div');
    row.className = 'price-row';
    row.innerHTML = `
      <div class="price-row-top">
        <span class="price-icon">${p.icon}</span>
        <div class="price-info">
          <div class="price-name">${p.name}${invLabel} ${trendHtml}</div>
          <div class="price-val">${price.toLocaleString('tr-TR')} TL</div>
        </div>
      </div>
      <div class="price-actions">
        <div class="qty-group">
          <button class="qty-btn-sm qty-btn-buy" onclick="buyProduct('${pid}',1)"  ${dis}>+1</button>
          <button class="qty-btn-sm qty-btn-buy" onclick="buyProduct('${pid}',5)"  ${dis}>+5</button>
          <button class="qty-btn-sm qty-btn-buy" onclick="buyProduct('${pid}',10)" ${dis}>+10</button>
          <button class="qty-btn-sm qty-btn-buy" onclick="buyMaxProduct('${pid}')" ${dis}>MAX</button>
        </div>
        <div class="qty-group">
          <button class="qty-btn-sm qty-btn-sell" onclick="sellProduct('${pid}',1)"    ${disSell}>-1</button>
          <button class="qty-btn-sm qty-btn-sell" onclick="sellProduct('${pid}',5)"    ${disSell}>-5</button>
          <button class="qty-btn-sm qty-btn-sell" onclick="sellProduct('${pid}',10)"   ${disSell}>-10</button>
          <button class="qty-btn-sm qty-btn-sell" onclick="sellAllProduct('${pid}')"   ${disSell}>HEPSİ</button>
        </div>
      </div>`;
    pl.appendChild(row);
  });

  // Governance banner + panel
  renderGovPanel(cid);

  // Garaj bölümü (sadece şehirdeyken)
  const garageEl  = document.getElementById('garage-content');
  const garageDiv = document.getElementById('panel-garage');
  const atCity    = !state.traveling && cid === state.position;
  if (atCity) {
    let garageHtml = '';
    const needed  = Math.ceil(MAX_ENERGY - state.energy);
    if (needed > 0) {
      const fuelCost = needed * 15;
      garageHtml += `<button onclick="refuelVehicle()" style="width:100%;margin-bottom:6px;padding:8px;background:#0f3460;border:1px solid #f5a623;color:#f5a623;border-radius:4px;cursor:pointer;font-size:12px">⚡ Yakıt Doldur (+${needed}) — ${fuelCost.toLocaleString('tr-TR')} TL</button>`;
    }
    TRUCK_TIERS.forEach((t, i) => {
      if (i <= state.truckTier) return;
      const ok = state.money >= t.cost;
      garageHtml += `<button onclick="upgradeTruck(${i})" ${ok?'':'disabled'} style="width:100%;margin-bottom:6px;padding:8px;background:#0f3460;border:1px solid ${ok?'#4ecca3':'#444'};color:${ok?'#4ecca3':'#555'};border-radius:4px;cursor:${ok?'pointer':'not-allowed'};font-size:12px">${t.icon} ${t.name} — ${t.cap}t — ${t.cost.toLocaleString('tr-TR')} TL</button>`;
    });
    if (!garageHtml) garageHtml = '<span style="color:#555;font-size:12px">Araç maksimum düzeyde, yakıt dolu.</span>';
    garageEl.innerHTML = garageHtml;
    garageDiv.style.display = 'block';
  } else {
    garageDiv.style.display = 'none';
  }
}

function updateHUD() {
  document.getElementById('hud-money').textContent =
    Math.round(state.money).toLocaleString('tr-TR') + ' TL';
  document.getElementById('hud-location').textContent =
    state.traveling ? `🚛 → ${CITIES[state.traveling.to]?.name||'?'}` :
                      (CITIES[state.position]?.name || state.position);
  const load = invLoad();
  const tier = TRUCK_TIERS[state.truckTier || 0];
  document.getElementById('hud-capacity').textContent =
    `${tier.icon} ${load}/${state.truckCapacity} ton`;
  const pct = Math.max(0, Math.min(100, Math.round(state.energy)));
  document.getElementById('hud-energy-val').textContent = pct;
  const bar = document.getElementById('hud-energy-bar');
  bar.style.width = pct + '%';
  bar.className = 'energy-fill' + (pct < 25 ? ' low' : '');
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

  // Energy recharge: +1/sec when not traveling
  if (!state.traveling && state.energy < MAX_ENERGY) {
    const elapsed = (now - (state.lastEnergyTick || now)) / 1000;
    state.energy = Math.min(MAX_ENERGY, state.energy + elapsed);
  }
  state.lastEnergyTick = now;

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
    // Eski kayıtlarda olmayan alanları varsayılanla doldur
    if (state.truckTier      === undefined) state.truckTier      = 0;
    if (state.truckCapacity  === undefined) state.truckCapacity  = TRUCK_TIERS[state.truckTier].cap;
    if (state.energy         === undefined) state.energy         = MAX_ENERGY;
    if (!state.lastEcoTick)  state.lastEcoTick  = Date.now();
    if (!state.lastNewsTime) state.lastNewsTime = Date.now() - NEWS_INTERVAL + 5000;
    // Kapasite her zaman tier ile uyumlu olsun
    state.truckCapacity = TRUCK_TIERS[state.truckTier].cap;
    refreshPrices();
  }

  setupMapEvents();
  initMarkers();
  updateHUD();
  updateInventoryBar();
  await loadCityGov();
  updateMarkers();
  openCityPanel(state.position);
  requestAnimationFrame(loop);

  // Auto-save every 2 min
  setInterval(saveGame, 2*60*1000);
  // Refresh city governance every 60s
  setInterval(loadCityGov, 60*1000);

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
