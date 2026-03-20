-- MAB demo cihaz: fiziksel MAC AA:BB:CC:DD:EE:FF
-- FreeRADIUS policy `nac_mab_normalize` (policy.d/nac_mab) User-Name / User-Password
-- degerlerini 12 hex kucuk harfe cevirir; radcheck ile eslesir.
-- PAP: kullanici adi ve parola (MAC) ayni — gercek ortamda port guvenligi + whitelist sarttir.

INSERT INTO radcheck (username, attribute, op, value)
SELECT 'aabbccddeeff', 'Cleartext-Password', ':=', 'aabbccddeeff'
WHERE NOT EXISTS (
  SELECT 1 FROM radcheck WHERE username = 'aabbccddeeff' AND attribute = 'Cleartext-Password'
);

-- Misafir VLAN (30) — employee ile karisikligi onlemek icin ayri grup
INSERT INTO radusergroup (username, groupname, priority)
SELECT 'aabbccddeeff', 'guest', 5
WHERE NOT EXISTS (
  SELECT 1 FROM radusergroup WHERE username = 'aabbccddeeff' AND groupname = 'guest'
);
