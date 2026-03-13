require('dotenv').config();
const express    = require('express');
const http       = require('http');
const { Server } = require('socket.io');
const cors       = require('cors');
const path       = require('path');
const pool       = require('./db/pool');
const fs         = require('fs');

const app    = express();
const server = http.createServer(app);
const io     = new Server(server, {
  cors: { origin: '*', methods: ['GET', 'POST'] },
});

// ── Middleware ─────────────────────────────────────────────
app.use(cors());
app.use(express.json({ limit: '2mb' }));
app.use(express.static(path.join(__dirname, '../public')));

// ── Health check ───────────────────────────────────────────
app.get('/api/health', (_req, res) => res.json({ ok: true, time: new Date() }));

// ── Routes ─────────────────────────────────────────────────
app.use('/api/auth',        require('./routes/auth'));
app.use('/api/game',        require('./routes/game'));
app.use('/api/leaderboard', require('./routes/leaderboard'));

// ── SPA fallbacks ──────────────────────────────────────────
app.get('/',            (_req, res) => res.sendFile(path.join(__dirname, '../public/login.html')));
app.get('/game',        (_req, res) => res.sendFile(path.join(__dirname, '../public/game.html')));
app.get('/leaderboard', (_req, res) => res.sendFile(path.join(__dirname, '../public/leaderboard.html')));

// ── Socket.io ──────────────────────────────────────────────
require('./socket/chat')(io);

// ── DB init + start ────────────────────────────────────────
async function start() {
  try {
    const schema = fs.readFileSync(path.join(__dirname, 'db/schema.sql'), 'utf8');
    await pool.query(schema);
    console.log('✓ Database schema OK');
  } catch (e) {
    console.error('DB schema error:', e.message);
  }

  const PORT = process.env.PORT || 3000;
  server.listen(PORT, () => {
    console.log(`🚛 Ticaretsim running → http://localhost:${PORT}`);
  });
}

start();
