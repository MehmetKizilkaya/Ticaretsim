const router  = require('express').Router();
const bcrypt  = require('bcryptjs');
const jwt     = require('jsonwebtoken');
const pool    = require('../db/pool');
const authMw  = require('../middleware/auth');

function makeToken(user) {
  return jwt.sign(
    { id: user.id, username: user.username },
    process.env.JWT_SECRET,
    { expiresIn: '30d' }
  );
}

// POST /api/auth/register
router.post('/register', async (req, res) => {
  const { username, email, password } = req.body || {};

  if (!username || !email || !password)
    return res.status(400).json({ error: 'Tüm alanlar zorunlu' });
  if (username.length < 3 || username.length > 30)
    return res.status(400).json({ error: 'Kullanıcı adı 3-30 karakter olmalı' });
  if (!/^[a-zA-Z0-9_]+$/.test(username))
    return res.status(400).json({ error: 'Kullanıcı adı sadece harf, rakam ve _ içerebilir' });
  if (password.length < 6)
    return res.status(400).json({ error: 'Şifre en az 6 karakter olmalı' });

  try {
    const hash = await bcrypt.hash(password, 12);
    const { rows } = await pool.query(
      'INSERT INTO users (username, email, password_hash) VALUES ($1, $2, $3) RETURNING id, username, email',
      [username.trim(), email.trim().toLowerCase(), hash]
    );
    const user = rows[0];
    res.status(201).json({ token: makeToken(user), user });
  } catch (e) {
    if (e.code === '23505') {
      if (e.constraint?.includes('username'))
        return res.status(400).json({ error: 'Bu kullanıcı adı zaten kullanılıyor' });
      if (e.constraint?.includes('email'))
        return res.status(400).json({ error: 'Bu e-posta zaten kayıtlı' });
    }
    console.error('Register error:', e.message);
    res.status(500).json({ error: 'Kayıt sırasında bir hata oluştu' });
  }
});

// POST /api/auth/login
router.post('/login', async (req, res) => {
  const { email, password } = req.body || {};
  if (!email || !password)
    return res.status(400).json({ error: 'E-posta ve şifre gerekli' });

  try {
    const { rows } = await pool.query('SELECT * FROM users WHERE email = $1', [email.trim().toLowerCase()]);
    const user = rows[0];
    if (!user) return res.status(401).json({ error: 'E-posta veya şifre hatalı' });

    const valid = await bcrypt.compare(password, user.password_hash);
    if (!valid) return res.status(401).json({ error: 'E-posta veya şifre hatalı' });

    await pool.query('UPDATE users SET last_seen = NOW() WHERE id = $1', [user.id]);
    res.json({
      token: makeToken(user),
      user: { id: user.id, username: user.username, email: user.email }
    });
  } catch (e) {
    console.error('Login error:', e.message);
    res.status(500).json({ error: 'Giriş sırasında bir hata oluştu' });
  }
});

// GET /api/auth/me  (protected)
router.get('/me', authMw, async (req, res) => {
  try {
    const { rows } = await pool.query(
      'SELECT id, username, email, created_at, last_seen FROM users WHERE id = $1',
      [req.user.id]
    );
    if (!rows[0]) return res.status(404).json({ error: 'Kullanıcı bulunamadı' });
    res.json(rows[0]);
  } catch {
    res.status(500).json({ error: 'Kullanıcı bilgisi alınamadı' });
  }
});

module.exports = router;
