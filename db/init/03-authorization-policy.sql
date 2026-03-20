-- Grup uyelikleri (kullanici -> grup)
INSERT INTO radusergroup (username, groupname, priority)
SELECT 'demo', 'employee', 1
WHERE NOT EXISTS (SELECT 1 FROM radusergroup WHERE username = 'demo' AND groupname = 'employee');

INSERT INTO radusergroup (username, groupname, priority)
SELECT 'chapuser', 'guest', 1
WHERE NOT EXISTS (SELECT 1 FROM radusergroup WHERE username = 'chapuser' AND groupname = 'guest');

-- Admin: PAP + MD5 (sifre: AdminPass!99)
INSERT INTO radcheck (username, attribute, op, value)
SELECT 'admin', 'MD5-Password', ':=', '865c5eff31b0294c23d26abcc1526b5c'
WHERE NOT EXISTS (SELECT 1 FROM radcheck WHERE username = 'admin' AND attribute = 'MD5-Password');

INSERT INTO radusergroup (username, groupname, priority)
SELECT 'admin', 'admin', 1
WHERE NOT EXISTS (SELECT 1 FROM radusergroup WHERE username = 'admin' AND groupname = 'admin');

-- Grup VLAN politikalari (802.1X / RADIUS tunnel attributes)
-- Bu satirlar rlm_sql read_groups=kapali iken yalnizca FastAPI /radius/authorize tarafindan okunur.
INSERT INTO radgroupreply (groupname, attribute, op, value)
SELECT 'admin', 'Tunnel-Type', ':=', 'VLAN'
WHERE NOT EXISTS (SELECT 1 FROM radgroupreply WHERE groupname = 'admin' AND attribute = 'Tunnel-Type');

INSERT INTO radgroupreply (groupname, attribute, op, value)
SELECT 'admin', 'Tunnel-Medium-Type', ':=', 'IEEE-802'
WHERE NOT EXISTS (SELECT 1 FROM radgroupreply WHERE groupname = 'admin' AND attribute = 'Tunnel-Medium-Type');

INSERT INTO radgroupreply (groupname, attribute, op, value)
SELECT 'admin', 'Tunnel-Private-Group-Id', ':=', '10'
WHERE NOT EXISTS (SELECT 1 FROM radgroupreply WHERE groupname = 'admin' AND attribute = 'Tunnel-Private-Group-Id');

INSERT INTO radgroupreply (groupname, attribute, op, value)
SELECT 'employee', 'Tunnel-Type', ':=', 'VLAN'
WHERE NOT EXISTS (SELECT 1 FROM radgroupreply WHERE groupname = 'employee' AND attribute = 'Tunnel-Type');

INSERT INTO radgroupreply (groupname, attribute, op, value)
SELECT 'employee', 'Tunnel-Medium-Type', ':=', 'IEEE-802'
WHERE NOT EXISTS (SELECT 1 FROM radgroupreply WHERE groupname = 'employee' AND attribute = 'Tunnel-Medium-Type');

INSERT INTO radgroupreply (groupname, attribute, op, value)
SELECT 'employee', 'Tunnel-Private-Group-Id', ':=', '20'
WHERE NOT EXISTS (SELECT 1 FROM radgroupreply WHERE groupname = 'employee' AND attribute = 'Tunnel-Private-Group-Id');

INSERT INTO radgroupreply (groupname, attribute, op, value)
SELECT 'guest', 'Tunnel-Type', ':=', 'VLAN'
WHERE NOT EXISTS (SELECT 1 FROM radgroupreply WHERE groupname = 'guest' AND attribute = 'Tunnel-Type');

INSERT INTO radgroupreply (groupname, attribute, op, value)
SELECT 'guest', 'Tunnel-Medium-Type', ':=', 'IEEE-802'
WHERE NOT EXISTS (SELECT 1 FROM radgroupreply WHERE groupname = 'guest' AND attribute = 'Tunnel-Medium-Type');

INSERT INTO radgroupreply (groupname, attribute, op, value)
SELECT 'guest', 'Tunnel-Private-Group-Id', ':=', '30'
WHERE NOT EXISTS (SELECT 1 FROM radgroupreply WHERE groupname = 'guest' AND attribute = 'Tunnel-Private-Group-Id');
