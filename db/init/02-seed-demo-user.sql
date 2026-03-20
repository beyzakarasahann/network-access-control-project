-- Demo user for PAP with hashed password (MD5-Password = MD5(password) as 32-char hex).
-- Login: demo / DemoPass123
-- Hash: printf 'DemoPass123' | md5   (or: md5 -qs DemoPass123 on macOS)
INSERT INTO radcheck (username, attribute, op, value)
SELECT 'demo', 'MD5-Password', ':=', '04c2677a12f9cd80d4497a0831d6f543'
WHERE NOT EXISTS (
  SELECT 1 FROM radcheck WHERE username = 'demo' AND attribute = 'MD5-Password'
);

-- CHAP (RFC 1994): server must derive CHAP-Response using the shared secret in plaintext.
-- One-way password hash in SQL cannot satisfy standard CHAP verification; this row is
-- ONLY for `radtest -t chap` lab demo. PAP + hashing requirement is met by `demo` above.
-- Login: chapuser / ChapPass789
INSERT INTO radcheck (username, attribute, op, value)
SELECT 'chapuser', 'Cleartext-Password', ':=', 'ChapPass789'
WHERE NOT EXISTS (
  SELECT 1 FROM radcheck WHERE username = 'chapuser' AND attribute = 'Cleartext-Password'
);
