const router = require('express').Router();
const pool   = require('../db/pool');
const authMw = require('../middleware/auth');

// GET /api/trade  — list active listings
router.get('/', async (req, res) => {
  try {
    const { rows } = await pool.query(`
      SELECT id, seller_id, seller_name, product_id, quantity, price_per, city_id, created_at
      FROM trade_listings
      WHERE active = TRUE AND expires_at > NOW()
      ORDER BY created_at DESC
      LIMIT 200
    `);
    res.json(rows);
  } catch (e) {
    console.error('Trade list error:', e.message);
    res.status(500).json({ error: 'İlanlar yüklenemedi' });
  }
});

// POST /api/trade  — create listing
router.post('/', authMw, async (req, res) => {
  const { product_id, quantity, price_per, city_id } = req.body || {};
  if (!product_id || !quantity || !price_per)
    return res.status(400).json({ error: 'Eksik veri' });
  if (quantity <= 0 || price_per <= 0)
    return res.status(400).json({ error: 'Geçersiz değer' });

  try {
    const { rows } = await pool.query(
      `INSERT INTO trade_listings (seller_id, seller_name, product_id, quantity, price_per, city_id)
       VALUES ($1, $2, $3, $4, $5, $6) RETURNING *`,
      [req.user.id, req.user.username, product_id, quantity, price_per, city_id || '']
    );
    res.status(201).json(rows[0]);
  } catch (e) {
    console.error('Trade create error:', e.message);
    res.status(500).json({ error: 'İlan oluşturulamadı' });
  }
});

// POST /api/trade/:id/buy  — buy from listing (server updates both players' game saves)
router.post('/:id/buy', authMw, async (req, res) => {
  const listingId = parseInt(req.params.id);
  const { quantity } = req.body || {};
  if (!quantity || quantity <= 0)
    return res.status(400).json({ error: 'Miktar belirtin' });

  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    // Lock listing row
    const { rows: listRows } = await client.query(
      'SELECT * FROM trade_listings WHERE id = $1 AND active = TRUE AND expires_at > NOW() FOR UPDATE',
      [listingId]
    );
    const listing = listRows[0];
    if (!listing) {
      await client.query('ROLLBACK');
      return res.status(404).json({ error: 'İlan bulunamadı veya süresi doldu' });
    }
    if (listing.seller_id === req.user.id) {
      await client.query('ROLLBACK');
      return res.status(400).json({ error: 'Kendi ilanınızdan alamazsınız' });
    }

    const qty   = Math.min(quantity, listing.quantity);
    const total = qty * listing.price_per;

    // Check buyer money
    const { rows: buyerRows } = await client.query(
      'SELECT game_state FROM game_saves WHERE user_id = $1 FOR UPDATE',
      [req.user.id]
    );
    const buyerSave = buyerRows[0];
    if (!buyerSave) {
      await client.query('ROLLBACK');
      return res.status(400).json({ error: 'Oyun veriniz bulunamadı — önce oyunu başlatın' });
    }
    const buyerState = buyerSave.game_state;
    if ((buyerState.money || 0) < total) {
      await client.query('ROLLBACK');
      return res.status(400).json({ error: 'Yeterli para yok' });
    }

    // Deduct money + add to buyer inventory
    buyerState.money = (buyerState.money || 0) - total;
    buyerState.inventory = buyerState.inventory || {};
    buyerState.inventory[listing.product_id] = (buyerState.inventory[listing.product_id] || 0) + qty;
    await client.query(
      'UPDATE game_saves SET game_state = $1, updated_at = NOW() WHERE user_id = $2',
      [JSON.stringify(buyerState), req.user.id]
    );

    // Add money to seller's game save
    const { rows: sellerRows } = await client.query(
      'SELECT game_state FROM game_saves WHERE user_id = $1 FOR UPDATE',
      [listing.seller_id]
    );
    if (sellerRows[0]) {
      const sellerState = sellerRows[0].game_state;
      sellerState.money = (sellerState.money || 0) + total;
      await client.query(
        'UPDATE game_saves SET game_state = $1, updated_at = NOW() WHERE user_id = $2',
        [JSON.stringify(sellerState), listing.seller_id]
      );
    }

    // Update listing quantity / deactivate
    const newQty = listing.quantity - qty;
    if (newQty <= 0) {
      await client.query('UPDATE trade_listings SET active = FALSE WHERE id = $1', [listingId]);
    } else {
      await client.query('UPDATE trade_listings SET quantity = $1 WHERE id = $2', [newQty, listingId]);
    }

    await client.query('COMMIT');
    res.json({
      ok: true, qty, total,
      product_id:   listing.product_id,
      newMoney:     buyerState.money,
      newInventory: buyerState.inventory,
    });
  } catch (e) {
    await client.query('ROLLBACK');
    console.error('Trade buy error:', e.message);
    res.status(500).json({ error: 'Satın alma başarısız' });
  } finally {
    client.release();
  }
});

// DELETE /api/trade/:id  — cancel own listing
router.delete('/:id', authMw, async (req, res) => {
  try {
    const { rows } = await pool.query(
      'UPDATE trade_listings SET active = FALSE WHERE id = $1 AND seller_id = $2 RETURNING id',
      [req.params.id, req.user.id]
    );
    if (!rows.length) return res.status(404).json({ error: 'İlan bulunamadı' });
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: 'İlan iptal edilemedi' });
  }
});

module.exports = router;
