-- 云雀漫剧 用户系统 schema (Neon Postgres)
-- 运行: 在 Neon SQL Editor (Vercel Dashboard → Storage → Neon → Query) 中粘贴执行

-- 1. 用户表 -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    tier          TEXT NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'pro')),
    pro_until     TIMESTAMPTZ,  -- 仅 tier='pro' 时有效; NULL = 不过期
    daily_limit_override INTEGER,  -- admin 强制覆盖每日额度 (NULL 走 tier 默认)
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (lower(email));

-- 2. 生成记录表 -------------------------------------------------------
CREATE TABLE IF NOT EXISTS generations (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id     TEXT NOT NULL,
    prompt      TEXT NOT NULL,
    ratio       TEXT,
    duration    TEXT,
    status      TEXT NOT NULL DEFAULT 'submitted', -- submitted / generating / done / failed
    video_url   TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_generations_user_date
    ON generations (user_id, created_at DESC);

-- 3. 视图：今日已用额度 (per user per UTC calendar day) -----------------
CREATE OR REPLACE VIEW v_user_quota_today AS
SELECT
    u.id AS user_id,
    u.email,
    u.tier,
    u.pro_until,
    COALESCE(u.daily_limit_override,
             CASE WHEN u.tier = 'pro' AND (u.pro_until IS NULL OR u.pro_until > NOW())
                  THEN 100
                  ELSE 1
             END) AS daily_limit,
    (SELECT COUNT(*) FROM generations g
     WHERE g.user_id = u.id
       AND g.created_at >= date_trunc('day', NOW() AT TIME ZONE 'UTC')
       AND g.status IN ('submitted', 'generating', 'done')) AS used_today
FROM users u;

-- 4. (可选) admin 用户：通过 SQL 升 Pro -------------------------------
-- 示例：把某用户升为 pro 30 天
-- UPDATE users SET tier='pro', pro_until=NOW() + INTERVAL '30 days' WHERE email='someone@example.com';
