-- ECDICT 离线英汉词库 — 独立 SQLite 数据库 word_lib.db
-- 字段与 skywind3000/ECDICT ecdict.csv 完全一致

CREATE TABLE IF NOT EXISTS word_lib (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word VARCHAR(128) NOT NULL,
    phonetic VARCHAR(128),
    definition TEXT,
    translation TEXT,
    pos VARCHAR(64),
    collins INTEGER DEFAULT 0,
    oxford INTEGER DEFAULT 0,
    tag VARCHAR(128),
    bnc INTEGER DEFAULT 0,
    frq INTEGER DEFAULT 0,
    exchange TEXT,
    detail TEXT,
    audio TEXT,
    -- AI 缓存补充字段（词库未命中时写入）
    ai_generated INTEGER DEFAULT 0,
    kaoyan_gloss TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_word_lib_word ON word_lib(word COLLATE NOCASE);
CREATE UNIQUE INDEX IF NOT EXISTS uq_word_lib_word ON word_lib(word COLLATE NOCASE);
