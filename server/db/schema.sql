-- Ticaretsim Database Schema

CREATE TABLE IF NOT EXISTS users (
  id            SERIAL PRIMARY KEY,
  username      VARCHAR(30) UNIQUE NOT NULL,
  email         VARCHAR(100) UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  last_seen     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS game_saves (
  id           SERIAL PRIMARY KEY,
  user_id      INTEGER REFERENCES users(id) ON DELETE CASCADE,
  game_state   JSONB NOT NULL,
  city_supply  JSONB NOT NULL,
  npc_state    JSONB NOT NULL DEFAULT '[]',
  updated_at   TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id)
);

CREATE TABLE IF NOT EXISTS chat_messages (
  id         SERIAL PRIMARY KEY,
  user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
  username   VARCHAR(30) NOT NULL,
  message    TEXT NOT NULL CHECK(length(message) <= 300),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS transactions (
  id         SERIAL PRIMARY KEY,
  user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
  city_id    VARCHAR(30) NOT NULL,
  product_id VARCHAR(20) NOT NULL,
  action     VARCHAR(4) NOT NULL CHECK(action IN ('buy','sell')),
  quantity   INTEGER NOT NULL,
  price      INTEGER NOT NULL,
  total      INTEGER NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Leaderboard index
CREATE INDEX IF NOT EXISTS idx_saves_money
  ON game_saves ((game_state->>'money')::numeric DESC);

-- Recent chat index
CREATE INDEX IF NOT EXISTS idx_chat_created
  ON chat_messages (created_at DESC);

-- User transactions index
CREATE INDEX IF NOT EXISTS idx_transactions_user
  ON transactions (user_id, created_at DESC);
