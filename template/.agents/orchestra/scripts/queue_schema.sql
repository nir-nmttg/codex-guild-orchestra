PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS queue_metadata (
  key TEXT NOT NULL PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS events (
  event_id TEXT NOT NULL PRIMARY KEY,
  timestamp TEXT NOT NULL,
  actor TEXT NOT NULL,
  event_type TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  entity_json TEXT NOT NULL,
  operation TEXT NOT NULL,
  workflow_id TEXT,
  structured_data_usage_json TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  event_safety_json TEXT NOT NULL,
  inserted_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_events_workflow_id ON events(workflow_id);
CREATE INDEX IF NOT EXISTS idx_events_entity ON events(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_events_event_type ON events(event_type);

CREATE TABLE IF NOT EXISTS quests (
  quest_id TEXT NOT NULL PRIMARY KEY,
  workflow_id TEXT,
  rank TEXT,
  status TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_quests_status ON quests(status);
CREATE INDEX IF NOT EXISTS idx_quests_workflow_id ON quests(workflow_id);

CREATE TABLE IF NOT EXISTS requests (
  request_id TEXT NOT NULL PRIMARY KEY,
  quest_id TEXT,
  workflow_id TEXT,
  status TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS commands (
  command_id TEXT NOT NULL PRIMARY KEY,
  quest_id TEXT,
  workflow_id TEXT,
  status TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS assignments (
  assignment_id TEXT NOT NULL PRIMARY KEY,
  parent_id TEXT,
  worker_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  workflow_id TEXT,
  status TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_assignments_worker_id ON assignments(worker_id);
CREATE INDEX IF NOT EXISTS idx_assignments_status ON assignments(status);
CREATE INDEX IF NOT EXISTS idx_assignments_workflow_id ON assignments(workflow_id);

CREATE TABLE IF NOT EXISTS reports (
  report_id TEXT NOT NULL PRIMARY KEY,
  worker_id TEXT NOT NULL,
  workflow_id TEXT,
  decision TEXT,
  status TEXT,
  payload_json TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_reports_worker_id ON reports(worker_id);
CREATE INDEX IF NOT EXISTS idx_reports_workflow_id ON reports(workflow_id);

CREATE TABLE IF NOT EXISTS trials (
  trial_id TEXT NOT NULL PRIMARY KEY,
  quest_id TEXT,
  workflow_id TEXT,
  depth TEXT,
  status TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_trials_quest_id ON trials(quest_id);
CREATE INDEX IF NOT EXISTS idx_trials_workflow_id ON trials(workflow_id);

CREATE TABLE IF NOT EXISTS inbox_messages (
  message_id TEXT NOT NULL PRIMARY KEY,
  recipient TEXT NOT NULL,
  workflow_id TEXT,
  status TEXT,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_inbox_recipient ON inbox_messages(recipient);
CREATE INDEX IF NOT EXISTS idx_inbox_status ON inbox_messages(status);
CREATE INDEX IF NOT EXISTS idx_inbox_workflow_id ON inbox_messages(workflow_id);
