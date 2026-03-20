-- radreply: kullaniciya ozel RADIUS cevap attribute (PDF 3.6 minimum tablo kullanimi ornegi)
-- Session-Timeout: VLAN / Tunnel attribute'lari ile cakismaz; oturum maksimum suresi (saniye).
-- demo kullanicisi zaten radusergroup ile employee + API authorize VLAN alir.

INSERT INTO radreply (username, attribute, op, value)
SELECT 'demo', 'Session-Timeout', ':=', '28800'
WHERE NOT EXISTS (
  SELECT 1 FROM radreply WHERE username = 'demo' AND attribute = 'Session-Timeout'
);
