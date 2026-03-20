import { fetchSnapshot } from "@/lib/snapshot";

// Build sirasinda API yok; statik hata sayfasi embed edilmesin — her istekte sunucuda fetch
export const dynamic = "force-dynamic";

function Pill({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className={`pill ${ok ? "ok" : "bad"}`}>{label}</span>
  );
}

export default async function Home() {
  const result = await fetchSnapshot();

  if (!result.ok) {
    return (
      <main>
        <h1>NAC Monitoring</h1>
        <p className="sub">
          FastAPI anlık verisi alınamadı. <strong>Docker:</strong>{" "}
          <code className="mono">docker compose ps</code> —{" "}
          <code className="mono">nac_api</code> ve <code className="mono">nac_monitoring</code>{" "}
          ayakta mı? Sonra:{" "}
          <code className="mono">docker compose up -d --build api monitoring</code>
          <br />
          <strong>API kodu güncelse:</strong>{" "}
          <code className="mono">curl http://localhost:8000/monitoring/snapshot</code> (hosttan)
          <br />
          <strong>Yerel Next:</strong>{" "}
          <code className="mono">INTERNAL_API_URL=http://127.0.0.1:8000 npm run dev</code>
        </p>
        <p className="error">Denenen istekler (sunucu logu):</p>
        <pre
          className="mono"
          style={{
            background: "var(--card)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            padding: "1rem",
            overflow: "auto",
            fontSize: "0.75rem",
            whiteSpace: "pre-wrap",
          }}
        >
          {result.detail}
        </pre>
      </main>
    );
  }

  const data = result.data;
  const h = data.health;
  const overall = h.status === "ok";

  return (
    <main>
      <h1>NAC Monitoring</h1>
      <p className="sub">
        S3M Staj — bonus: monitoring dashboard · Veri kaynağı: FastAPI{" "}
        <span className="mono">/monitoring/snapshot</span> · canlı veri (önbellek yok)
      </p>

      <div className="grid">
        <div className="card">
          <h2>Sistem durumu</h2>
          <p>
            <Pill ok={overall} label={overall ? "Healthy" : "Degraded"} />
          </p>
          <p style={{ marginTop: "0.75rem", fontSize: "0.9rem" }}>
            Postgres: <Pill ok={h.postgres} label={h.postgres ? "OK" : "DOWN"} />
            <span style={{ marginLeft: "0.5rem" }} />
            Redis: <Pill ok={h.redis} label={h.redis ? "OK" : "DOWN"} />
          </p>
          <p className="mono" style={{ marginTop: "0.5rem", color: "var(--muted)" }}>
            API v{data.api_version}
          </p>
        </div>

        <div className="card">
          <h2>Aktif oturum (Redis)</h2>
          <div className="big">{data.sessions.count}</div>
          <p className="mono" style={{ color: "var(--muted)", marginTop: "0.35rem" }}>
            nac:acct:* ≈ {data.redis_metrics.nac_acct_keys}
            {data.redis_metrics.nac_acct_keys_truncated ? "+" : ""} anahtar
          </p>
          {data.sessions.error && (
            <p className="error">Redis oturum: {data.sessions.error}</p>
          )}
        </div>

        <div className="card">
          <h2>Kullanıcı kayıtları</h2>
          <div className="big">{data.users.radcheck_count}</div>
          <p style={{ color: "var(--muted)", fontSize: "0.9rem" }}>
            radusergroup: {data.users.radusergroup_count} satır
          </p>
          {data.users.error && (
            <p className="error">{data.users.error}</p>
          )}
        </div>

        <div className="card">
          <h2>Accounting (PostgreSQL)</h2>
          <div className="big">{data.accounting.radacct_rows}</div>
          <p style={{ color: "var(--muted)", fontSize: "0.9rem" }}>
            Açık oturum (DB): {data.accounting.open_sessions_db}
          </p>
          {data.accounting.error && (
            <p className="error">{data.accounting.error}</p>
          )}
        </div>

        <div className="card">
          <h2>Rate limit (Redis)</h2>
          <div className="big">{data.redis_metrics.auth_fail_keys}</div>
          <p className="mono" style={{ color: "var(--muted)", fontSize: "0.85rem" }}>
            nac_auth_fail_* sayacları
            {data.redis_metrics.auth_fail_keys_truncated ? " (≥500)" : ""}
          </p>
        </div>
      </div>

      <div className="card" style={{ marginTop: "1.25rem" }}>
        <h2>Son accounting kayıtları</h2>
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th>Kullanıcı</th>
                <th>NAS</th>
                <th>Başlangıç</th>
                <th>Bitiş</th>
                <th>Süre (sn)</th>
                <th>In/Out octets</th>
              </tr>
            </thead>
            <tbody>
              {data.accounting.recent.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ color: "var(--muted)" }}>
                    Kayıt yok
                  </td>
                </tr>
              ) : (
                data.accounting.recent.map((r, i) => (
                  <tr key={i}>
                    <td>{r.username ?? "—"}</td>
                    <td className="mono">{r.nas_ip ?? "—"}</td>
                    <td className="mono">{r.acct_start ?? "—"}</td>
                    <td className="mono">{r.acct_stop ?? "—"}</td>
                    <td>{r.session_time}</td>
                    <td className="mono">
                      {r.in_octets} / {r.out_octets}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {data.sessions.items.length > 0 && (
        <div className="card" style={{ marginTop: "1.25rem" }}>
          <h2>Redis oturum önbelleği (özet)</h2>
          <table>
            <thead>
              <tr>
                <th>Unique ID</th>
                <th>Kullanıcı</th>
                <th>NAS</th>
                <th>Session</th>
              </tr>
            </thead>
            <tbody>
              {data.sessions.items.slice(0, 15).map((s, i) => (
                <tr key={i}>
                  <td className="mono">{(s.acct_unique_session_id as string) ?? "—"}</td>
                  <td>{(s.username as string) ?? "—"}</td>
                  <td className="mono">{(s.nas_ip as string) ?? "—"}</td>
                  <td className="mono">{(s.acct_session_id as string) ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="timestamp">Son güncelleme (API): {data.timestamp}</p>
    </main>
  );
}
