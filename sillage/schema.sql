PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
INSERT OR IGNORE INTO schema_version VALUES(1);
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL, password TEXT NOT NULL, preferences TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS single_owner_registration
BEFORE INSERT ON users WHEN EXISTS(SELECT 1 FROM users)
BEGIN
    SELECT RAISE(ABORT, 'Registration is closed.');
END;
INSERT OR IGNORE INTO schema_version VALUES(3);
CREATE TABLE IF NOT EXISTS fragrances(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, data TEXT NOT NULL, archived INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS recommendations(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, created_at TEXT NOT NULL, snapshot TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS wears(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, fragrance_id INTEGER NOT NULL REFERENCES fragrances(id), recommendation_id INTEGER REFERENCES recommendations(id), created_at TEXT NOT NULL, snapshot TEXT NOT NULL, feedback TEXT);
CREATE INDEX IF NOT EXISTS wear_user ON wears(user_id,created_at);
CREATE INDEX IF NOT EXISTS recommendation_user ON recommendations(user_id,created_at);
CREATE UNIQUE INDEX IF NOT EXISTS single_wear_per_recommendation ON wears(recommendation_id);
CREATE TABLE IF NOT EXISTS catalog_metadata(provider TEXT NOT NULL, external_id TEXT NOT NULL, retrieved_at TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(provider, external_id));
CREATE UNIQUE INDEX IF NOT EXISTS collection_catalog_identity ON fragrances(user_id,json_extract(data,'$.metadata.provider'),json_extract(data,'$.metadata.external_id')) WHERE archived=0 AND json_extract(data,'$.metadata.external_id') IS NOT NULL;
INSERT OR IGNORE INTO schema_version VALUES(2);
CREATE UNIQUE INDEX IF NOT EXISTS collection_variant_identity ON fragrances(user_id,json_extract(data,'$.metadata.identity')) WHERE archived=0 AND json_extract(data,'$.metadata.identity') IS NOT NULL;
