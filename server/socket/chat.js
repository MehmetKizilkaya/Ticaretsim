const jwt  = require('jsonwebtoken');
const pool = require('../db/pool');

const onlineUsers = new Map(); // socketId → { id, username }

module.exports = (io) => {
  io.on('connection', (socket) => {
    let currentUser = null;

    // ── Auth ──────────────────────────────────────────────
    socket.on('chat:join', async ({ token } = {}) => {
      try {
        const payload = jwt.verify(token, process.env.JWT_SECRET);
        currentUser = { id: payload.id, username: payload.username };
        onlineUsers.set(socket.id, currentUser);

        // Send last 50 messages
        const { rows } = await pool.query(
          `SELECT username, message, created_at
           FROM chat_messages
           ORDER BY created_at DESC LIMIT 50`
        );
        socket.emit('chat:history', rows.reverse());

        // Broadcast updated online count
        io.emit('chat:online', onlineUsers.size);

        // Update last_seen
        pool.query('UPDATE users SET last_seen = NOW() WHERE id = $1', [currentUser.id])
          .catch(() => {});
      } catch {
        socket.emit('chat:error', 'Giriş gerekli');
      }
    });

    // ── Send message ─────────────────────────────────────
    socket.on('chat:message', async ({ text } = {}) => {
      if (!currentUser) return socket.emit('chat:error', 'Giriş gerekli');
      const clean = String(text || '').trim().slice(0, 300);
      if (!clean) return;

      try {
        await pool.query(
          'INSERT INTO chat_messages (user_id, username, message) VALUES ($1, $2, $3)',
          [currentUser.id, currentUser.username, clean]
        );
        io.emit('chat:message', {
          username:   currentUser.username,
          text:       clean,
          ts:         new Date().toISOString(),
        });
      } catch (e) {
        console.error('Chat DB error:', e.message);
      }
    });

    // ── Disconnect ───────────────────────────────────────
    socket.on('disconnect', () => {
      onlineUsers.delete(socket.id);
      io.emit('chat:online', onlineUsers.size);
    });
  });
};
