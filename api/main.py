"""
NAC policy engine — FastAPI + FreeRADIUS (authorize rlm_rest), accounting, Redis cache.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any, Literal

import psycopg
import redis
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

app = FastAPI(title="NAC Policy Engine", version="0.2.0")


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
    return {"message": "NAC API calisiyor"}


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
