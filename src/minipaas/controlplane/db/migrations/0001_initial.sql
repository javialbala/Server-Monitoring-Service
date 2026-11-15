-- Esquema inicial (Fase 2). Las fechas son texto ISO 8601 en UTC con segundos.

-- Usuarios del panel. Hoy habrá un único administrador (ADR-010), pero la tabla ya admite más.
-- El nombre no distingue mayúsculas (COLLATE NOCASE) para que "Admin" y "admin" sean el mismo.
-- password_hash guarda el hash Argon2id completo (incluye sal y parámetros), nunca la contraseña.
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  username TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK (length(username) BETWEEN 3 AND 64),
  password_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Sesiones del panel guardadas en servidor (se pueden revocar de verdad).
CREATE TABLE sessions (
  id INTEGER PRIMARY KEY,
  token_hash TEXT NOT NULL UNIQUE,          -- SHA-256 (hex) del identificador; el identificador en claro solo está en la cookie
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  csrf_token TEXT NOT NULL,                 -- token sincronizador CSRF de esta sesión
  created_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,                 -- caducidad absoluta
  revoked_at TEXT
);
CREATE INDEX idx_sessions_user ON sessions(user_id);

-- Estados lógicos de una aplicación. Es una tabla de códigos y no un CHECK para que las
-- fases futuras añadan estados con un simple INSERT en una migración, sin reconstruir la tabla.
CREATE TABLE application_statuses (code TEXT PRIMARY KEY, description TEXT NOT NULL);
INSERT INTO application_statuses VALUES ('draft', 'Sin desplegar');

-- Aplicaciones registradas. El slug es el identificador público e inmutable (base de los
-- nombres DNS/Docker de la Fase 3).
CREATE TABLE applications (
  id INTEGER PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE CHECK (length(slug) BETWEEN 3 AND 40),
  name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 100),
  description TEXT NOT NULL DEFAULT '' CHECK (length(description) <= 500),
  status TEXT NOT NULL DEFAULT 'draft' REFERENCES application_statuses(code),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Registro de auditoría: quién hizo qué y con qué resultado. Nunca contiene secretos.
CREATE TABLE audit_events (
  id INTEGER PRIMARY KEY,
  occurred_at TEXT NOT NULL,
  event_type TEXT NOT NULL,
  outcome TEXT NOT NULL CHECK (outcome IN ('success', 'failure')),
  user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  resource_type TEXT,
  resource_id TEXT,                         -- texto, sin FK: el evento sobrevive al borrado del recurso
  client_ip TEXT,
  metadata TEXT NOT NULL DEFAULT '{}'       -- JSON con datos NO sensibles
);
CREATE INDEX idx_audit_occurred ON audit_events(occurred_at);
