"""
NAC policy engine — FastAPI + FreeRADIUS (authorize rlm_rest), accounting, Redis cache.
"""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from typing import Any, Literal

import psycopg
import redis
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

app = FastAPI(title="NAC Policy Engine", version="0.2.2")


def _pg_connect():
    return psycopg.connect(
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=5,
    )


def _redis() -> redis.Redis:
    return redis.Redis(
        host=os.environ.get("REDIS_HOST", "redis"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
        decode_responses=True,
        socket_connect_timeout=3,
    )


def _redis_session_key(unique_id: str) -> str:
    return f"nac:acct:{unique_id}"


def _redis_set_session(
    r: redis.Redis,
    unique_id: str,
    username: str,
    nas_ip: str,
    session_id: str,
    in_octets: int,
    out_octets: int,
    session_time: int,
    ttl: int = 7200,
) -> None:
    val = f"{username}|{nas_ip}|{session_id}|{in_octets}|{out_octets}|{session_time}"
    r.set(_redis_session_key(unique_id), val, ex=ttl)


def _redis_del_session(r: redis.Redis, unique_id: str) -> None:
    r.delete(_redis_session_key(unique_id))


def _extract_username(body: dict[str, Any]) -> str | None:
    for key in ("User-Name", "Stripped-User-Name"):
        block = body.get(key)
        if isinstance(block, dict):
            vals = block.get("value")
            if isinstance(vals, list) and vals:
                u = vals[0]
                if isinstance(u, str) and u.strip():
                    return u.strip()
    return None


def _group_reply_to_rest_json(rows: list[tuple[str, str, str]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for attr, value, op in rows:
        op = (op or ":=").strip()
        if op not in (":=", "+=", "="):
            op = ":="
        out[attr] = {"value": [value], "op": op}
    return out


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class AuthRequest(BaseModel):
    username: str
    password: str


class AccountingRequest(BaseModel):
    """HTTP accounting (curl / harici test). FreeRADIUS ayrica kendi sql ile yazar."""

    model_config = ConfigDict(populate_by_name=True)

    status: Literal["Start", "Interim-Update", "Stop"] = Field(
        validation_alias=AliasChoices("status", "Acct-Status-Type")
    )
    username: str = Field(validation_alias=AliasChoices("username", "User-Name"))
    acct_session_id: str = Field(
        validation_alias=AliasChoices("acct_session_id", "Acct-Session-Id")
    )
    acct_unique_session_id: str = Field(
        validation_alias=AliasChoices("acct_unique_session_id", "Acct-Unique-Session-Id")
    )
    nas_ip_address: str = Field(
        validation_alias=AliasChoices("nas_ip_address", "NAS-IP-Address")
    )
    acct_input_octets: int = Field(
        0, validation_alias=AliasChoices("acct_input_octets", "Acct-Input-Octets")
    )
    acct_output_octets: int = Field(
        0, validation_alias=AliasChoices("acct_output_octets", "Acct-Output-Octets")
    )
    acct_session_time: int | None = Field(
        None, validation_alias=AliasChoices("acct_session_time", "Acct-Session-Time")
    )
    acct_terminate_cause: str | None = Field(
        None, validation_alias=AliasChoices("acct_terminate_cause", "Acct-Terminate-Cause")
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/")
def root():
    return {
        "message": "NAC API calisiyor",
        "version": "0.2.2",
        "monitoring": "/monitoring/snapshot",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    """Postgres + Redis baglantisi (compose / monitoring icin)."""
    pg_ok = False
    redis_ok = False
    try:
        with _pg_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        pg_ok = True
    except Exception:
        pass
    try:
        _redis().ping()
        redis_ok = True
    except Exception:
        pass

    body: dict[str, Any] = {
        "status": "ok" if (pg_ok and redis_ok) else "degraded",
        "postgres": pg_ok,
        "redis": redis_ok,
    }
    if pg_ok and redis_ok:
        return body
    return JSONResponse(status_code=503, content=body)


def _collect_active_sessions() -> tuple[list[dict[str, Any]], str | None]:
    """Redis aktif oturum listesi; hata mesaji veya None."""
    try:
        r = _redis()
        out: list[dict[str, Any]] = []
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor, match="nac:acct:*", count=200)
            for k in keys:
                raw = r.get(k)
                if not raw:
                    continue
                parts = raw.split("|")
                uid = k.split(":", 2)[-1] if ":" in k else k
                item: dict[str, Any] = {"acct_unique_session_id": uid, "raw": raw}
                if len(parts) >= 6:
                    item.update(
                        {
                            "username": parts[0],
                            "nas_ip": parts[1],
                            "acct_session_id": parts[2],
                            "acct_input_octets": int(parts[3] or 0),
                            "acct_output_octets": int(parts[4] or 0),
                            "acct_session_time": int(parts[5] or 0),
                        }
                    )
                out.append(item)
            if cursor == 0:
                break
        return out, None
    except Exception as e:
        return [], str(e)


def _redis_count_pattern(match: str, limit: int = 500) -> tuple[int, bool]:
    """SCAN ile anahtar sayisi; limit asildiyse truncated=True."""
    try:
        r = _redis()
        n = 0
        cursor = 0
        truncated = False
        while True:
            cursor, keys = r.scan(cursor, match=match, count=200)
            n += len(keys)
            if n >= limit:
                truncated = True
                break
            if cursor == 0:
                break
        return min(n, limit), truncated
    except Exception:
        return 0, False


@app.get("/monitoring/snapshot")
def monitoring_snapshot():
    """
    Next.js / monitoring dashboard icin tek JSON.
    Odev bonus: monitoring dashboard.
    """
    ts = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    snap: dict[str, Any] = {
        "timestamp": ts,
        "api_version": "0.2.2",
        "health": {"postgres": False, "redis": False, "status": "degraded"},
        "sessions": {"count": 0, "items": [], "error": None},
        "users": {"radcheck_count": 0, "radusergroup_count": 0, "error": None},
        "accounting": {
            "radacct_rows": 0,
            "open_sessions_db": 0,
            "recent": [],
            "error": None,
        },
        "redis_metrics": {
            "nac_acct_keys": 0,
            "nac_acct_keys_truncated": False,
            "auth_fail_keys": 0,
            "auth_fail_keys_truncated": False,
        },
    }

    try:
        with _pg_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            snap["health"]["postgres"] = True
    except Exception:
        pass

    try:
        _redis().ping()
        snap["health"]["redis"] = True
    except Exception:
        pass

    if snap["health"]["postgres"] and snap["health"]["redis"]:
        snap["health"]["status"] = "ok"

    items, s_err = _collect_active_sessions()
    snap["sessions"]["items"] = items[:50]
    snap["sessions"]["count"] = len(items)
    snap["sessions"]["error"] = s_err

    n_acct, tr1 = _redis_count_pattern("nac:acct:*", 500)
    n_fail, tr2 = _redis_count_pattern("nac_auth_fail_*", 500)
    snap["redis_metrics"]["nac_acct_keys"] = n_acct
    snap["redis_metrics"]["nac_acct_keys_truncated"] = tr1
    snap["redis_metrics"]["auth_fail_keys"] = n_fail
    snap["redis_metrics"]["auth_fail_keys_truncated"] = tr2

    if not snap["health"]["postgres"]:
        snap["users"]["error"] = "database_unavailable"
        snap["accounting"]["error"] = "database_unavailable"
        return snap

    try:
        with _pg_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM radcheck")
                snap["users"]["radcheck_count"] = int(cur.fetchone()[0])
                cur.execute("SELECT COUNT(*) FROM radusergroup")
                snap["users"]["radusergroup_count"] = int(cur.fetchone()[0])
                cur.execute("SELECT COUNT(*) FROM radacct")
                snap["accounting"]["radacct_rows"] = int(cur.fetchone()[0])
                cur.execute(
                    "SELECT COUNT(*) FROM radacct WHERE acctstoptime IS NULL"
                )
                snap["accounting"]["open_sessions_db"] = int(cur.fetchone()[0])
                cur.execute(
                    """
                    SELECT username, nasipaddress::text, acctstarttime, acctstoptime,
                           acctsessiontime, acctinputoctets, acctoutputoctets
                    FROM radacct
                    ORDER BY radacctid DESC
                    LIMIT 8
                    """
                )
                recent = []
                for row in cur.fetchall():
                    recent.append(
                        {
                            "username": row[0],
                            "nas_ip": row[1],
                            "acct_start": row[2].isoformat() if row[2] else None,
                            "acct_stop": row[3].isoformat() if row[3] else None,
                            "session_time": int(row[4] or 0),
                            "in_octets": int(row[5] or 0),
                            "out_octets": int(row[6] or 0),
                        }
                    )
                snap["accounting"]["recent"] = recent
    except Exception as e:
        snap["users"]["error"] = str(e)
        snap["accounting"]["error"] = str(e)

    return snap


@app.post("/authorize")
def authorize(body: dict[str, Any]):
    username = _extract_username(body)
    if not username:
        return Response(status_code=204)

    sql = """
        SELECT g.attribute, g.value, g.op
        FROM radusergroup u
        JOIN radgroupreply g ON LOWER(u.groupname) = LOWER(g.groupname)
        WHERE u.username = %s
        ORDER BY u.priority, g.id
    """
    try:
        with _pg_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (username,))
                rows = cur.fetchall()
    except Exception:
        return JSONResponse(status_code=503, content={"error": "database_unavailable"})

    if not rows:
        return Response(status_code=204)

    payload = _group_reply_to_rest_json([(r[0], r[1], r[2]) for r in rows])
    return JSONResponse(content=payload)


@app.post("/auth")
def auth(req: AuthRequest):
    """Basit kimlik kontrolu (PAP ile uyumlu: MD5-Password veya Cleartext-Password)."""
    try:
        with _pg_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT attribute, value FROM radcheck
                    WHERE username = %s AND attribute IN ('MD5-Password', 'Cleartext-Password')
                    """,
                    (req.username,),
                )
                rows = cur.fetchall()
    except Exception:
        return JSONResponse(status_code=503, content={"ok": False, "error": "database_unavailable"})

    if not rows:
        return JSONResponse(status_code=401, content={"ok": False, "reason": "unknown_user"})

    ok = False
    for attr, value in rows:
        if attr == "Cleartext-Password" and value == req.password:
            ok = True
            break
        if attr == "MD5-Password":
            digest = hashlib.md5(req.password.encode("utf-8")).hexdigest()
            if digest.lower() == (value or "").lower():
                ok = True
                break

    if not ok:
        return JSONResponse(status_code=401, content={"ok": False, "reason": "bad_password"})
    return {"ok": True, "username": req.username}


@app.get("/users")
def list_users():
    """radcheck + radusergroup ozeti (parola degerleri maskelenir)."""
    try:
        with _pg_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT username, attribute,
                           CASE WHEN attribute ILIKE '%password%' THEN '***' ELSE value END AS value
                    FROM radcheck ORDER BY username, id
                    """
                )
                checks = [
                    {"username": r[0], "attribute": r[1], "value": r[2]} for r in cur.fetchall()
                ]
                cur.execute(
                    """
                    SELECT username, groupname, priority FROM radusergroup ORDER BY username, priority
                    """
                )
                groups = [
                    {"username": r[0], "group": r[1], "priority": r[2]} for r in cur.fetchall()
                ]
    except Exception:
        return JSONResponse(status_code=503, content={"error": "database_unavailable"})

    return {"radcheck": checks, "radusergroup": groups}


@app.get("/sessions/active")
def sessions_active():
    """Redis'teki aktif oturum ozeti (FreeRADIUS accounting policy ile doldurulur)."""
    try:
        r = _redis()
        out: list[dict[str, Any]] = []
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor, match="nac:acct:*", count=200)
            for k in keys:
                raw = r.get(k)
                if not raw:
                    continue
                parts = raw.split("|")
                uid = k.split(":", 2)[-1] if ":" in k else k
                item: dict[str, Any] = {"acct_unique_session_id": uid, "raw": raw}
                if len(parts) >= 6:
                    item.update(
                        {
                            "username": parts[0],
                            "nas_ip": parts[1],
                            "acct_session_id": parts[2],
                            "acct_input_octets": int(parts[3] or 0),
                            "acct_output_octets": int(parts[4] or 0),
                            "acct_session_time": int(parts[5] or 0),
                        }
                    )
                out.append(item)
            if cursor == 0:
                break
    except Exception as e:
        return JSONResponse(status_code=503, content={"error": "redis_unavailable", "detail": str(e)})

    return {"count": len(out), "sessions": out}


@app.post("/accounting")
def accounting_http(req: AccountingRequest):
    """
    Accounting kaydi (PostgreSQL radacct + Redis).
    FreeRADIUS zaten sql ile yazar; bu endpoint bagimsiz test / entegrasyon icin.
    """
    status = req.status
    u = req.username
    sid = req.acct_session_id
    uid = req.acct_unique_session_id
    nas = req.nas_ip_address
    tin = req.acct_input_octets
    tout = req.acct_output_octets
    st = req.acct_session_time

    try:
        r = _redis()
        with _pg_connect() as conn:
            with conn.cursor() as cur:
                if status == "Start":
                    cur.execute(
                        """
                        INSERT INTO radacct (
                            acctsessionid, acctuniqueid, username, nasipaddress,
                            acctstarttime, acctupdatetime, acctinputoctets, acctoutputoctets
                        ) VALUES (%s, %s, %s, %s::inet, NOW(), NOW(), %s, %s)
                        ON CONFLICT (acctuniqueid) DO UPDATE SET
                            acctupdatetime = NOW(),
                            acctinputoctets = EXCLUDED.acctinputoctets,
                            acctoutputoctets = EXCLUDED.acctoutputoctets
                        """,
                        (sid, uid, u, nas, tin, tout),
                    )
                    _redis_set_session(r, uid, u, nas, sid, tin, tout, st or 0)

                elif status == "Interim-Update":
                    cur.execute(
                        """
                        UPDATE radacct SET
                            acctupdatetime = NOW(),
                            acctinputoctets = %s,
                            acctoutputoctets = %s,
                            acctsessiontime = COALESCE(%s, acctsessiontime)
                        WHERE acctuniqueid = %s AND acctstoptime IS NULL
                        """,
                        (tin, tout, st, uid),
                    )
                    _redis_set_session(r, uid, u, nas, sid, tin, tout, st or 0)

                elif status == "Stop":
                    cur.execute(
                        """
                        UPDATE radacct SET
                            acctstoptime = NOW(),
                            acctupdatetime = NOW(),
                            acctinputoctets = %s,
                            acctoutputoctets = %s,
                            acctsessiontime = COALESCE(%s, acctsessiontime),
                            acctterminatecause = COALESCE(%s, 'User-Request')
                        WHERE acctuniqueid = %s AND acctstoptime IS NULL
                        """,
                        (tin, tout, st, req.acct_terminate_cause, uid),
                    )
                    _redis_del_session(r, uid)

            conn.commit()
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

    return {"ok": True, "status": status, "acct_unique_session_id": uid}
