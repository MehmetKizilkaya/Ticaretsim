const router = require('express').Router();
const pool   = require('../db/pool');

// GET /api/leaderboard  → top 50 players by money
router.get('/', async (req, res) => {
  try {
    const { rows } = await pool.query(`
      SELECT
        u.id,
        u.username,
        (gs.game_state->>'money')::numeric AS money,
        gs.updated_at
      FROM game_saves gs
      JOIN users u ON u.id = gs.user_id
      WHERE gs.game_state->>'money' IS NOT NULL
      ORDER BY money DESC
      LIMIT 50
    `);
    res.json(
      rows.map((r, i) => ({
        rank:       i + 1,
        id:         r.id,
        username:   r.username,
        money:      Math.round(r.money),
        updated_at: r.updated_at,
      }))
    );
  } catch (e) {
    console.error('Leaderboard error:', e.message);
    res.status(500).json({ error: 'Liderboard yüklenemedi' });
  }
});

module.exports = router;
