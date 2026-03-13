const router = require('express').Router();
const pool   = require('../db/pool');
const authMw = require('../middleware/auth');

// GET /api/game/state  → load saved game
router.get('/state', authMw, async (req, res) => {
  try {
    const { rows } = await pool.query(
      'SELECT game_state, city_supply, npc_state FROM game_saves WHERE user_id = $1',
      [req.user.id]
    );
    if (!rows.length) return res.json(null);  // fresh start
    const r = rows[0];
    res.json({ state: r.game_state, citySupply: r.city_supply, npcs: r.npc_state });
  } catch (e) {
    console.error('Load error:', e.message);
    res.status(500).json({ error: 'Kayıt yüklenemedi' });
  }
});

// POST /api/game/save  → upsert game state
router.post('/save', authMw, async (req, res) => {
  const { state, citySupply, npcs } = req.body || {};
  if (!state || !citySupply)
    return res.status(400).json({ error: 'Eksik veri' });

  try {
    await pool.query(
      `INSERT INTO game_saves (user_id, game_state, city_supply, npc_state)
       VALUES ($1, $2, $3, $4)
       ON CONFLICT (user_id) DO UPDATE
         SET game_state  = EXCLUDED.game_state,
             city_supply = EXCLUDED.city_supply,
             npc_state   = EXCLUDED.npc_state,
             updated_at  = NOW()`,
      [req.user.id, JSON.stringify(state), JSON.stringify(citySupply), JSON.stringify(npcs || [])]
    );
    res.json({ ok: true });
  } catch (e) {
    console.error('Save error:', e.message);
    res.status(500).json({ error: 'Kayıt kaydedilemedi' });
  }
});

// POST /api/game/transaction  → log a buy/sell
router.post('/transaction', authMw, async (req, res) => {
  const { city_id, product_id, action, quantity, price } = req.body || {};
  if (!city_id || !product_id || !action || !quantity || !price)
    return res.status(400).json({ error: 'Eksik işlem verisi' });

  try {
    await pool.query(
      `INSERT INTO transactions (user_id, city_id, product_id, action, quantity, price, total)
       VALUES ($1, $2, $3, $4, $5, $6, $7)`,
      [req.user.id, city_id, product_id, action, quantity, price, quantity * price]
    );
    res.json({ ok: true });
  } catch (e) {
    console.error('Transaction log error:', e.message);
    res.status(500).json({ error: 'İşlem kaydedilemedi' });
  }
});

// GET /api/game/history  → last 100 transactions
router.get('/history', authMw, async (req, res) => {
  try {
    const { rows } = await pool.query(
      `SELECT city_id, product_id, action, quantity, price, total, created_at
       FROM transactions WHERE user_id = $1
       ORDER BY created_at DESC LIMIT 100`,
      [req.user.id]
    );
    res.json(rows);
  } catch {
    res.status(500).json({ error: 'Geçmiş yüklenemedi' });
  }
});

module.exports = router;
