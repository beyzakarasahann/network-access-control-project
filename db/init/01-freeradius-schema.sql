CREATE TABLE IF NOT EXISTS radacct (
  RadAcctId BIGSERIAL PRIMARY KEY,
  AcctSessionId TEXT NOT NULL,
  AcctUniqueId TEXT NOT NULL UNIQUE,
  UserName TEXT,
  Realm TEXT,
  NASIPAddress INET NOT NULL,
  NASPortId TEXT,
  NASPortType TEXT,
  AcctStartTime TIMESTAMPTZ,
  AcctUpdateTime TIMESTAMPTZ,
  AcctStopTime TIMESTAMPTZ,
  AcctInterval BIGINT,
  AcctSessionTime BIGINT,
  AcctAuthentic TEXT,
  ConnectInfo_start TEXT,
  ConnectInfo_stop TEXT,
  AcctInputOctets BIGINT,
  AcctOutputOctets BIGINT,
  CalledStationId TEXT,
  CallingStationId TEXT,
  AcctTerminateCause TEXT,
  ServiceType TEXT,
  FramedProtocol TEXT,
  FramedIPAddress INET,
  FramedIPv6Address INET,
  FramedIPv6Prefix INET,
  FramedInterfaceId TEXT,
  DelegatedIPv6Prefix INET,
  Class TEXT
);

CREATE INDEX IF NOT EXISTS radacct_active_session_idx ON radacct (AcctUniqueId) WHERE AcctStopTime IS NULL;
CREATE INDEX IF NOT EXISTS radacct_bulk_close ON radacct (NASIPAddress, AcctStartTime) WHERE AcctStopTime IS NULL;
CREATE INDEX IF NOT EXISTS radacct_start_user_idx ON radacct (AcctStartTime, UserName);

CREATE TABLE IF NOT EXISTS radcheck (
  id SERIAL PRIMARY KEY,
  UserName TEXT NOT NULL DEFAULT '',
  Attribute TEXT NOT NULL DEFAULT '',
  op VARCHAR(2) NOT NULL DEFAULT '==',
  Value TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS radcheck_username_idx ON radcheck (UserName, Attribute);

CREATE TABLE IF NOT EXISTS radreply (
  id SERIAL PRIMARY KEY,
  UserName TEXT NOT NULL DEFAULT '',
  Attribute TEXT NOT NULL DEFAULT '',
  op VARCHAR(2) NOT NULL DEFAULT '=',
  Value TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS radreply_username_idx ON radreply (UserName, Attribute);

CREATE TABLE IF NOT EXISTS radusergroup (
  id SERIAL PRIMARY KEY,
  UserName TEXT NOT NULL DEFAULT '',
  GroupName TEXT NOT NULL DEFAULT '',
  priority INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS radusergroup_username_idx ON radusergroup (UserName);

CREATE TABLE IF NOT EXISTS radgroupreply (
  id SERIAL PRIMARY KEY,
  GroupName TEXT NOT NULL DEFAULT '',
  Attribute TEXT NOT NULL DEFAULT '',
  op VARCHAR(2) NOT NULL DEFAULT '=',
  Value TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS radgroupreply_groupname_idx ON radgroupreply (GroupName, Attribute);

CREATE TABLE IF NOT EXISTS radgroupcheck (
  id SERIAL PRIMARY KEY,
  GroupName TEXT NOT NULL DEFAULT '',
  Attribute TEXT NOT NULL DEFAULT '',
  op VARCHAR(2) NOT NULL DEFAULT '==',
  Value TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS radgroupcheck_groupname_idx ON radgroupcheck (GroupName, Attribute);

CREATE TABLE IF NOT EXISTS radpostauth (
  id BIGSERIAL PRIMARY KEY,
  username TEXT NOT NULL,
  pass TEXT,
  reply TEXT,
  CalledStationId TEXT,
  CallingStationId TEXT,
  authdate TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  Class TEXT
);

CREATE TABLE IF NOT EXISTS nas (
  id SERIAL PRIMARY KEY,
  nasname TEXT NOT NULL,
  shortname TEXT NOT NULL,
  type TEXT NOT NULL DEFAULT 'other',
  ports INTEGER,
  secret TEXT NOT NULL,
  server TEXT,
  community TEXT,
  description TEXT
);
CREATE INDEX IF NOT EXISTS nas_nasname_idx ON nas (nasname);
