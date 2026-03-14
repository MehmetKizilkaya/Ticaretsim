'use strict';
const router = require('express').Router();
const pool   = require('../db/pool');
const authMw = require('../middleware/auth');

// ── City base values (TL) ───────────────────────────────────
const BASE_VALUES = {
  istanbul:500000, ankara:300000, izmir:250000,
  bursa:150000, antalya:150000, konya:120000, kocaeli:120000,
  adana:100000, mersin:100000, gaziantep:100000,
  samsun:80000,  trabzon:80000,  diyarbakir:80000, erzurum:80000,
  malatya:60000, batman:60000,   van:60000,
};
function baseValue(cityId) { return BASE_VALUES[cityId] || 40000; }

// ── Happiness formula (computed, not stored) ────────────────
// happiness = 50 + tradeBonus(max30) - taxPenalty - infraBonus(max36)
async function computeHappiness(cityId, stats) {
  const { rows } = await pool.query(
    `SELECT COUNT(*) AS cnt FROM transactions
     WHERE city_id = $1 AND created_at > NOW() - INTERVAL '7 days'`,
    [cityId]
  );
  const trades     = parseInt(rows[0].cnt) || 0;
  const tradeBonus = Math.min(30, trades * 3);
  const taxPenalty = Math.max(0, (stats.tax_rate - 5) * 4);
  const infraSum   = (stats.infra_storage||0) + (stats.infra_road||0) +
                     (stats.infra_market||0)  + (stats.infra_factory||0);
  const infraBonus = infraSum * 3;
  return Math.max(0, Math.min(100, 50 + tradeBonus - taxPenalty + infraBonus));
}

// ── Ensure city_stats row exists ───────────────────────────
async function ensureStats(cityId) {
  await pool.query(
    `INSERT INTO city_stats (city_id) VALUES ($1) ON CONFLICT (city_id) DO NOTHING`,
    [cityId]
  );
}

// ── Helper: read / write game_state money ──────────────────
async function getGameMoney(userId) {
  const { rows } = await pool.query(
    'SELECT game_state FROM game_saves WHERE user_id = $1', [userId]
  );
  if (!rows.length) return null;
  return rows[0].game_state;
}
async function setGameMoney(userId, gs) {
  await pool.query(
    'UPDATE game_saves SET game_state = $1, updated_at = NOW() WHERE user_id = $2',
    [JSON.stringify(gs), userId]
  );
}

// ============================================================
// GET /api/cities  —  all ownerships (lightweight, for map)
// ============================================================
router.get('/', async (_req, res) => {
  try {
    const { rows } = await pool.query(`
      SELECT co.city_id, co.owner_id, co.owner_name,
             co.protected_until, co.claimed_at,
             cs.tax_rate, cs.treasury,
             cs.infra_storage, cs.infra_road, cs.infra_market, cs.infra_factory
      FROM   city_ownership co
      LEFT JOIN city_stats cs ON cs.city_id = co.city_id
    `);
    res.json(rows);
  } catch (e) {
    console.error('cities list error:', e.message);
    res.status(500).json({ error: 'Şehir listesi alınamadı' });
  }
});

// ============================================================
// GET /api/cities/:id  —  full city detail
// ============================================================
router.get('/:id', async (req, res) => {
  const cityId = req.params.id;
  try {
    await ensureStats(cityId);
    const [ownerR, statsR, auctR] = await Promise.all([
      pool.query('SELECT * FROM city_ownership WHERE city_id = $1', [cityId]),
      pool.query('SELECT * FROM city_stats WHERE city_id = $1', [cityId]),
      pool.query(`
        SELECT * FROM city_auctions
        WHERE city_id = $1 AND resolved = FALSE AND ends_at > NOW()
        ORDER BY created_at DESC LIMIT 1
      `, [cityId]),
    ]);
    const stats     = statsR.rows[0];
    const happiness = await computeHappiness(cityId, stats);
    res.json({
      ownership:  ownerR.rows[0] || null,
      stats:      { ...stats, happiness },
      auction:    auctR.rows[0]  || null,
      baseValue:  baseValue(cityId),
    });
  } catch (e) {
    console.error('city detail error:', e.message);
    res.status(500).json({ error: 'Şehir detayı alınamadı' });
  }
});

// ============================================================
// POST /api/cities/:id/claim  —  buy unclaimed city
// ============================================================
router.post('/:id/claim', authMw, async (req, res) => {
  const cityId   = req.params.id;
  const userId   = req.user.id;
  const username = req.user.username;
  try {
    const { rows: ex } = await pool.query(
      'SELECT city_id FROM city_ownership WHERE city_id = $1', [cityId]
    );
    if (ex.length) return res.status(400).json({ error: 'Bu şehir zaten birine ait' });

    const dipLvl  = Math.min(3, parseInt(req.body?.diplomaticLevel) || 0);
    const dipDisc = [0, 0.15, 0.25, 0.35][dipLvl];
    const cost    = Math.round(baseValue(cityId) * (1 - dipDisc));
    const gs      = await getGameMoney(userId);
    if (!gs) return res.status(400).json({ error: 'Oyun kaydı bulunamadı' });
    if ((gs.money || 0) < cost)
      return res.status(400).json({ error: `Yeterli para yok! Gereken: ${cost.toLocaleString('tr-TR')} TL` });

    gs.money -= cost;
    await setGameMoney(userId, gs);

    const prot = new Date(Date.now() + 12 * 3600 * 1000);
    await ensureStats(cityId);
    await pool.query(
      `INSERT INTO city_ownership (city_id, owner_id, owner_name, purchase_price, protected_until)
       VALUES ($1,$2,$3,$4,$5)`,
      [cityId, userId, username, cost, prot]
    );

    // Seed treasury with 20% of purchase price
    await pool.query(
      'UPDATE city_stats SET treasury = $1 WHERE city_id = $2',
      [Math.round(cost * 0.2), cityId]
    );

    res.json({ ok: true, cost, newMoney: gs.money });
  } catch (e) {
    console.error('claim error:', e.message);
    res.status(500).json({ error: 'Şehir alımı başarısız' });
  }
});

// ============================================================
// POST /api/cities/:id/tax  —  set tax rate (mayor only)
// ============================================================
router.post('/:id/tax', authMw, async (req, res) => {
  const cityId = req.params.id;
  const userId = req.user.id;
  const rate   = parseInt(req.body.rate);
  if (isNaN(rate) || rate < 0 || rate > 15)
    return res.status(400).json({ error: 'Vergi oranı 0-15 arasında olmalı' });
  try {
    const { rows } = await pool.query(
      'SELECT owner_id FROM city_ownership WHERE city_id = $1', [cityId]
    );
    if (!rows.length || rows[0].owner_id !== userId)
      return res.status(403).json({ error: 'Bu şehrin başkanı değilsiniz' });

    await ensureStats(cityId);
    await pool.query(
      'UPDATE city_stats SET tax_rate=$1, updated_at=NOW() WHERE city_id=$2',
      [rate, cityId]
    );
    res.json({ ok: true, rate });
  } catch (e) {
    res.status(500).json({ error: 'Vergi ayarı başarısız' });
  }
});

// ============================================================
// POST /api/cities/:id/invest  —  infrastructure (mayor, from treasury)
// ============================================================
const INFRA_COSTS = {
  storage: [30000, 50000, 100000],
  road:    [20000, 40000,  80000],
  market:  [25000, 45000,  90000],
  factory: [40000, 70000, 130000],
};
router.post('/:id/invest', authMw, async (req, res) => {
  const cityId = req.params.id;
  const userId = req.user.id;
  const { type } = req.body;
  if (!INFRA_COSTS[type])
    return res.status(400).json({ error: 'Geçersiz altyapı türü' });
  try {
    const { rows: ownerR } = await pool.query(
      'SELECT owner_id FROM city_ownership WHERE city_id = $1', [cityId]
    );
    if (!ownerR.length || ownerR[0].owner_id !== userId)
      return res.status(403).json({ error: 'Bu şehrin başkanı değilsiniz' });

    await ensureStats(cityId);
    const { rows: statsR } = await pool.query(
      'SELECT * FROM city_stats WHERE city_id = $1', [cityId]
    );
    const stats = statsR[0];
    const col   = `infra_${type}`;
    const lvl   = stats[col] || 0;
    if (lvl >= 3) return res.status(400).json({ error: 'Maksimum seviyeye ulaşıldı' });

    const cost = INFRA_COSTS[type][lvl];
    if ((stats.treasury || 0) < cost)
      return res.status(400).json({ error: `Hazine yetersiz! Gereken: ${cost.toLocaleString('tr-TR')} TL` });

    await pool.query(
      `UPDATE city_stats SET ${col}=${col}+1, treasury=treasury-$1, updated_at=NOW() WHERE city_id=$2`,
      [cost, cityId]
    );
    res.json({ ok: true, newLevel: lvl + 1, cost, treasury: stats.treasury - cost });
  } catch (e) {
    console.error('invest error:', e.message);
    res.status(500).json({ error: 'Yatırım başarısız' });
  }
});

// ============================================================
// POST /api/cities/:id/tax-payment  —  add trade tax to treasury
// ============================================================
router.post('/:id/tax-payment', authMw, async (req, res) => {
  const cityId = req.params.id;
  const amount = parseInt(req.body.amount) || 0;
  if (amount <= 0) return res.json({ ok: true });
  try {
    await ensureStats(cityId);
    await pool.query(
      'UPDATE city_stats SET treasury=treasury+$1, updated_at=NOW() WHERE city_id=$2',
      [amount, cityId]
    );
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: 'Vergi ödemesi başarısız' });
  }
});

// ============================================================
// POST /api/cities/:id/collect  —  mayor withdraws 80% of treasury
// ============================================================
router.post('/:id/collect', authMw, async (req, res) => {
  const cityId = req.params.id;
  const userId = req.user.id;
  try {
    const { rows: ownerR } = await pool.query(
      'SELECT owner_id FROM city_ownership WHERE city_id = $1', [cityId]
    );
    if (!ownerR.length || ownerR[0].owner_id !== userId)
      return res.status(403).json({ error: 'Bu şehrin başkanı değilsiniz' });

    const { rows: statsR } = await pool.query(
      'SELECT treasury FROM city_stats WHERE city_id = $1', [cityId]
    );
    const treasury = statsR[0]?.treasury || 0;
    if (treasury < 1000)
      return res.status(400).json({ error: 'Hazinede yeterli para yok (min 1.000 TL)' });

    const payout = Math.round(treasury * 0.8);
    const gs = await getGameMoney(userId);
    if (!gs) return res.status(400).json({ error: 'Oyun kaydı bulunamadı' });
    gs.money += payout;
    await setGameMoney(userId, gs);
    await pool.query(
      'UPDATE city_stats SET treasury=treasury-$1, updated_at=NOW() WHERE city_id=$2',
      [payout, cityId]
    );
    res.json({ ok: true, payout, newMoney: gs.money });
  } catch (e) {
    console.error('collect error:', e.message);
    res.status(500).json({ error: 'Vergi toplanamadı' });
  }
});

// ============================================================
// POST /api/cities/:id/auction/start  —  start overthrow auction
// ============================================================
router.post('/:id/auction/start', authMw, async (req, res) => {
  const cityId   = req.params.id;
  const userId   = req.user.id;
  try {
    const { rows: ownerR } = await pool.query(
      'SELECT * FROM city_ownership WHERE city_id = $1', [cityId]
    );
    if (!ownerR.length)
      return res.status(400).json({ error: 'Bu şehir sahipsiz, direkt satın alabilirsiniz' });

    const owner = ownerR[0];
    if (owner.protected_until && new Date(owner.protected_until) > new Date())
      return res.status(400).json({ error: 'Şehir koruma altında, henüz devrilme başlatılamaz' });

    const { rows: activeR } = await pool.query(
      `SELECT id FROM city_auctions WHERE city_id=$1 AND resolved=FALSE AND ends_at>NOW()`,
      [cityId]
    );
    if (activeR.length) return res.status(400).json({ error: 'Zaten aktif bir müzayede var' });

    await ensureStats(cityId);
    const { rows: statsR } = await pool.query(
      'SELECT * FROM city_stats WHERE city_id = $1', [cityId]
    );
    const stats     = statsR[0];
    const happiness = await computeHappiness(cityId, stats);

    let triggerCost = 0;
    const triggerType = happiness < 25 ? 'happiness' : 'challenge';

    if (triggerType === 'challenge') {
      triggerCost = Math.round(baseValue(cityId) * 0.15);
      const gs = await getGameMoney(userId);
      if (!gs) return res.status(400).json({ error: 'Oyun kaydı bulunamadı' });
      if ((gs.money || 0) < triggerCost)
        return res.status(400).json({ error: `Yeterli para yok! Devrilme bedeli: ${triggerCost.toLocaleString('tr-TR')} TL` });
      gs.money -= triggerCost;
      await setGameMoney(userId, gs);
    }

    const endsAt = new Date(Date.now() + 24 * 3600 * 1000);
    await pool.query(
      `INSERT INTO city_auctions (city_id, triggered_by, trigger_type, trigger_cost, ends_at)
       VALUES ($1,$2,$3,$4,$5)`,
      [cityId, userId, triggerType, triggerCost, endsAt]
    );
    res.json({ ok: true, endsAt, triggerCost, triggerType, happiness });
  } catch (e) {
    console.error('auction start error:', e.message);
    res.status(500).json({ error: 'Müzayede başlatılamadı' });
  }
});

// ============================================================
// POST /api/cities/:id/auction/bid  —  place bid
// ============================================================
router.post('/:id/auction/bid', authMw, async (req, res) => {
  const cityId   = req.params.id;
  const userId   = req.user.id;
  const username = req.user.username;
  const amount   = parseInt(req.body.amount);
  if (!amount || amount <= 0)
    return res.status(400).json({ error: 'Geçersiz teklif miktarı' });
  try {
    const { rows: auctR } = await pool.query(
      `SELECT * FROM city_auctions
       WHERE city_id=$1 AND resolved=FALSE AND ends_at>NOW()
       ORDER BY created_at DESC LIMIT 1`,
      [cityId]
    );
    if (!auctR.length) return res.status(400).json({ error: 'Aktif müzayede bulunamadı' });
    const auction = auctR[0];

    const { rows: ownerR } = await pool.query(
      'SELECT owner_id FROM city_ownership WHERE city_id=$1', [cityId]
    );
    if (ownerR.length && ownerR[0].owner_id === userId)
      return res.status(400).json({ error: 'Kendi şehrinize teklif veremezsiniz' });

    if (amount <= auction.top_bid)
      return res.status(400).json({ error: `Mevcut tekliften yüksek olmalı: ${auction.top_bid.toLocaleString('tr-TR')} TL` });

    const gs = await getGameMoney(userId);
    if (!gs) return res.status(400).json({ error: 'Oyun kaydı bulunamadı' });
    if ((gs.money || 0) < amount)
      return res.status(400).json({ error: 'Yeterli para yok!' });

    await pool.query(
      `UPDATE city_auctions SET top_bidder_id=$1, top_bidder_name=$2, top_bid=$3 WHERE id=$4`,
      [userId, username, amount, auction.id]
    );
    res.json({ ok: true, bid: amount });
  } catch (e) {
    console.error('bid error:', e.message);
    res.status(500).json({ error: 'Teklif verilemedi' });
  }
});

// ============================================================
// POST /api/cities/:id/auction/resolve  —  resolve expired auction
// ============================================================
router.post('/:id/auction/resolve', authMw, async (req, res) => {
  const cityId = req.params.id;
  try {
    const { rows: auctR } = await pool.query(
      `SELECT * FROM city_auctions
       WHERE city_id=$1 AND resolved=FALSE AND ends_at<=NOW()
       ORDER BY created_at DESC LIMIT 1`,
      [cityId]
    );
    if (!auctR.length) return res.status(400).json({ error: 'Çözülecek müzayede yok' });
    const auction = auctR[0];

    await pool.query('UPDATE city_auctions SET resolved=TRUE WHERE id=$1', [auction.id]);

    if (!auction.top_bidder_id)
      return res.json({ ok: true, result: 'no_bids', message: 'Teklif gelmedi, mevcut başkan devam ediyor' });

    // Deduct from winner
    const gs = await getGameMoney(auction.top_bidder_id);
    if (gs) {
      gs.money = Math.max(0, (gs.money || 0) - auction.top_bid);
      await setGameMoney(auction.top_bidder_id, gs);
    }

    // Transfer city (12h protection)
    const prot = new Date(Date.now() + 12 * 3600 * 1000);
    await pool.query(
      `INSERT INTO city_ownership (city_id, owner_id, owner_name, purchase_price, protected_until)
       VALUES ($1,$2,$3,$4,$5)
       ON CONFLICT (city_id) DO UPDATE
       SET owner_id=$2, owner_name=$3, purchase_price=$4, claimed_at=NOW(), protected_until=$5`,
      [cityId, auction.top_bidder_id, auction.top_bidder_name, auction.top_bid, prot]
    );

    // 20% of bid → city treasury
    await pool.query(
      'UPDATE city_stats SET treasury=treasury+$1, updated_at=NOW() WHERE city_id=$2',
      [Math.round(auction.top_bid * 0.2), cityId]
    );

    res.json({ ok: true, result: 'transferred', winner: auction.top_bidder_name, amount: auction.top_bid });
  } catch (e) {
    console.error('resolve error:', e.message);
    res.status(500).json({ error: 'Müzayede çözümlenemedi' });
  }
});

// ============================================================
// GET /api/cities/governance  — presidency + regional governors
// ============================================================
router.get('/governance', async (_req, res) => {
  try {
    const { rows } = await pool.query(`
      SELECT co.city_id, co.owner_id, co.owner_name, co.claimed_at,
             cs.treasury, cs.tax_rate, cs.infra_storage, cs.infra_road,
             cs.infra_market, cs.infra_factory
      FROM city_ownership co
      LEFT JOIN city_stats cs ON cs.city_id = co.city_id
      WHERE co.owner_id IS NOT NULL
    `);

    // Count cities per player
    const players = {};
    rows.forEach(r => {
      if (!players[r.owner_id]) {
        players[r.owner_id] = { id: r.owner_id, name: r.owner_name, cities: 0, treasury: 0 };
      }
      players[r.owner_id].cities++;
      players[r.owner_id].treasury += r.treasury || 0;
    });

    const ranked = Object.values(players).sort((a, b) => b.cities - a.cities);
    const president = ranked[0] || null;

    // Active auctions
    const { rows: auctions } = await pool.query(`
      SELECT id, city_id, top_bidder_name, top_bid, ends_at, trigger_type
      FROM city_auctions WHERE resolved = FALSE ORDER BY created_at DESC
    `);

    res.json({
      president,
      ranked,
      cityMap: rows.map(r => ({
        city_id:    r.city_id,
        owner_id:   r.owner_id,
        owner_name: r.owner_name,
        treasury:   r.treasury || 0,
        tax_rate:   r.tax_rate || 0,
        infra:      (r.infra_storage||0)+(r.infra_road||0)+(r.infra_market||0)+(r.infra_factory||0),
      })),
      auctions,
    });
  } catch (e) {
    console.error('governance error:', e.message);
    res.status(500).json({ error: 'Yönetim verisi yüklenemedi' });
  }
});

// ============================================================
// POST /api/cities/:id/claim  — updated to accept diplomaticLevel
// ============================================================
// (already defined above — the diplomatic discount is applied in the existing claim route)

module.exports = router;
