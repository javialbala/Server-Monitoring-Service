-- Fase 3: servicios, revisiones de despliegue y su bitácora. Migración no destructiva: solo
-- añade tablas, una columna y códigos de estado; los datos de la Fase 2 no se tocan.

-- Estado LÓGICO de la aplicación (lo que el administrador espera que ocurra). El estado real
-- de los contenedores NO se guarda aquí: se pregunta siempre al agente.
INSERT INTO application_statuses VALUES ('running', 'En funcionamiento');
INSERT INTO application_statuses VALUES ('stopped', 'Detenida');
INSERT INTO application_statuses VALUES ('attention', 'Requiere intervención');

-- Ciclo de vida de cada revisión de despliegue.
CREATE TABLE deployment_statuses (code TEXT PRIMARY KEY, description TEXT NOT NULL);
INSERT INTO deployment_statuses VALUES ('pending', 'Creada');
INSERT INTO deployment_statuses VALUES ('preparing', 'En preparación');
INSERT INTO deployment_statuses VALUES ('deploying', 'Desplegando');
INSERT INTO deployment_statuses VALUES ('healthy', 'Funcionando');
INSERT INTO deployment_statuses VALUES ('stopped', 'Detenida');
INSERT INTO deployment_statuses VALUES ('superseded', 'Sustituida');
INSERT INTO deployment_statuses VALUES ('discarded', 'Descartada');
INSERT INTO deployment_statuses VALUES ('failed', 'Fallida');
INSERT INTO deployment_statuses VALUES ('rolling_back', 'Recuperando versión anterior');
INSERT INTO deployment_statuses VALUES ('rolled_back', 'Fallida · versión anterior recuperada');
INSERT INTO deployment_statuses VALUES ('rollback_failed', 'Requiere intervención');
INSERT INTO deployment_statuses VALUES ('interrupted', 'Interrumpida');

-- Servicios que componen una aplicación: es la configuración EDITABLE (borrador). Al desplegar
-- se copia a deployment_services. `env` es JSON con solo las variables que permite el catálogo;
-- sus valores no se escriben nunca en logs ni en la auditoría.
CREATE TABLE services (
  id INTEGER PRIMARY KEY,
  application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
  name TEXT NOT NULL CHECK (length(name) BETWEEN 2 AND 30),
  catalog_id TEXT NOT NULL,
  internal_port INTEGER NOT NULL,
  host_port INTEGER UNIQUE CHECK (host_port IS NULL OR host_port BETWEEN 20000 AND 20999),
  env TEXT NOT NULL DEFAULT '{}',
  memory_mb INTEGER NOT NULL,
  cpus REAL NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (application_id, name)
);

-- Una fila = una revisión de despliegue de una aplicación. `operation_id` (UUID4) identifica la
-- operación en el agente (etiquetas de sus contenedores); `request_id` deduplica las peticiones
-- repetidas del cliente. `error` es un resumen no sensible.
CREATE TABLE deployments (
  id INTEGER PRIMARY KEY,
  application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
  revision INTEGER NOT NULL CHECK (revision >= 1),
  operation_id TEXT NOT NULL UNIQUE,
  request_id TEXT NOT NULL,
  status TEXT NOT NULL REFERENCES deployment_statuses(code),
  previous_deployment_id INTEGER REFERENCES deployments(id),
  error TEXT,
  created_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT,
  UNIQUE (application_id, revision),
  UNIQUE (application_id, request_id)
);

-- Exclusión mutua en la propia base de datos: como mucho UNA operación en curso por aplicación.
CREATE UNIQUE INDEX one_operation_per_app ON deployments(application_id)
  WHERE status IN ('preparing', 'deploying', 'rolling_back');

-- Configuración INMUTABLE de cada servicio en una revisión: el historial no cambia aunque el
-- servicio se edite o se borre después.
CREATE TABLE deployment_services (
  id INTEGER PRIMARY KEY,
  deployment_id INTEGER NOT NULL REFERENCES deployments(id) ON DELETE CASCADE,
  service_name TEXT NOT NULL,
  catalog_id TEXT NOT NULL,
  image_ref TEXT NOT NULL,
  internal_port INTEGER NOT NULL,
  host_port INTEGER,
  env TEXT NOT NULL,
  memory_mb INTEGER NOT NULL,
  cpus REAL NOT NULL,
  UNIQUE (deployment_id, service_name)
);

CREATE TRIGGER deployment_services_immutable BEFORE UPDATE ON deployment_services
BEGIN
  SELECT RAISE(ABORT, 'La configuración de una revisión es inmutable');
END;

-- Bitácora paso a paso de cada operación (se muestra en el panel).
CREATE TABLE deployment_events (
  id INTEGER PRIMARY KEY,
  deployment_id INTEGER NOT NULL REFERENCES deployments(id) ON DELETE CASCADE,
  occurred_at TEXT NOT NULL,
  step TEXT NOT NULL,
  outcome TEXT NOT NULL CHECK (outcome IN ('info', 'success', 'failure')),
  message TEXT NOT NULL
);

-- Revisión actualmente activa de la aplicación (NULL: nunca se desplegó con éxito).
ALTER TABLE applications ADD COLUMN active_deployment_id INTEGER DEFAULT NULL
  REFERENCES deployments(id);
