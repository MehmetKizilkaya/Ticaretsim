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

CREATE TABLE IF NOT EXISTS city_ownership (
  city_id         VARCHAR(30) PRIMARY KEY,
  owner_id        INTEGER REFERENCES users(id) ON DELETE SET NULL,
  owner_name      VARCHAR(30) NOT NULL DEFAULT '',
  purchase_price  INTEGER NOT NULL DEFAULT 0,
  claimed_at      TIMESTAMPTZ DEFAULT NOW(),
  protected_until TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS city_stats (
  city_id       VARCHAR(30) PRIMARY KEY,
  treasury      INTEGER NOT NULL DEFAULT 0,
  tax_rate      INTEGER NOT NULL DEFAULT 5,
  infra_storage INTEGER NOT NULL DEFAULT 0,
  infra_road    INTEGER NOT NULL DEFAULT 0,
  infra_market  INTEGER NOT NULL DEFAULT 0,
  infra_factory INTEGER NOT NULL DEFAULT 0,
  updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS city_auctions (
  id              SERIAL PRIMARY KEY,
  city_id         VARCHAR(30) NOT NULL,
  triggered_by    INTEGER REFERENCES users(id) ON DELETE SET NULL,
  trigger_type    VARCHAR(20) NOT NULL DEFAULT 'challenge',
  trigger_cost    INTEGER NOT NULL DEFAULT 0,
  top_bidder_id   INTEGER REFERENCES users(id) ON DELETE SET NULL,
  top_bidder_name VARCHAR(30),
  top_bid         INTEGER NOT NULL DEFAULT 0,
  ends_at         TIMESTAMPTZ NOT NULL,
  resolved        BOOLEAN NOT NULL DEFAULT FALSE,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Leaderboard index
CREATE INDEX IF NOT EXISTS idx_saves_money
  ON game_saves (CAST(game_state->>'money' AS numeric) DESC);

-- Recent chat index
CREATE INDEX IF NOT EXISTS idx_chat_created
  ON chat_messages (created_at DESC);

-- User transactions index
CREATE INDEX IF NOT EXISTS idx_transactions_user
  ON transactions (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS trade_listings (
  id          SERIAL PRIMARY KEY,
  seller_id   INTEGER REFERENCES users(id) ON DELETE CASCADE,
  seller_name VARCHAR(30) NOT NULL,
  product_id  VARCHAR(20) NOT NULL,
  quantity    INTEGER NOT NULL CHECK(quantity > 0),
  price_per   INTEGER NOT NULL CHECK(price_per > 0),
  city_id     VARCHAR(30) NOT NULL DEFAULT '',
  active      BOOLEAN NOT NULL DEFAULT TRUE,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  expires_at  TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '7 days'
);

CREATE INDEX IF NOT EXISTS idx_trade_active
  ON trade_listings (active, expires_at DESC);
