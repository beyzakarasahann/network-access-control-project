import type { ReactNode } from "react";
import { fetchSnapshot } from "@/lib/snapshot";
import {
  formatDataVolume,
  formatDateTime,
  formatDurationSeconds,
  formatUpdatedAt,
  shortenSessionId,
  simplifyNas,
} from "@/lib/format";

export const dynamic = "force-dynamic";

function Pill({ ok, label }: { ok: boolean; label: string }) {
  return <span className={`pill ${ok ? "ok" : "bad"}`}>{label}</span>;
}

function CardHint({ children }: { children: ReactNode }) {
  return <p className="card-hint">{children}</p>;
}

function SectionTitle({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="section-head">
      <h2 className="section-title">{title}</h2>
      <p className="section-desc">{description}</p>
    </div>
  );
}

export default async function Home() {
  const result = await fetchSnapshot();

  if (!result.ok) {
    return (
      <main>
        <h1>Ağ erişim izleme paneli</h1>
        <p className="sub">
          Sunucuya bağlanılamadı. <strong>Docker:</strong>{" "}
          <code className="mono">docker compose ps</code> —{" "}
          <code className="mono">nac_api</code> ve{" "}
          <code className="mono">nac_monitoring</code> çalışıyor mu? Ardından:{" "}
          <code className="mono">docker compose up -d --build api monitoring</code>
          <br />
          <strong>API testi:</strong>{" "}
          <code className="mono">curl http://localhost:8000/monitoring/snapshot</code>
          <br />
          <strong>Yerel Next:</strong>{" "}
          <code className="mono">INTERNAL_API_URL=http://127.0.0.1:8000 npm run dev</code>
        </p>
        <p className="error">Teknik ayrıntı:</p>
        <pre className="error-box">{result.detail}</pre>
      </main>
    );
  }

  const data = result.data;
  const h = data.health;
  const overall = h.status === "ok";

  return (
    <main>
      <header className="page-header">
        <h1>Ağ erişim izleme paneli</h1>
        <p className="lead">
          Bu ekran, <strong>NAC (Network Access Control)</strong> altyapınızın anlık özetini
          gösterir: kullanıcı veritabanı, bağlı oturumlar ve son bağlantı kayıtları. Veriler
          birkaç saniyede bir sunucudan yenilenir.
        </p>
      </header>

      <div className="grid">
        <div className="card card--accent">
          <h2 className="card-title">Genel durum</h2>
          <CardHint>
            Tüm parçalar çalışıyorsa aşağıda &quot;Hazır&quot; görünür. Biri kırmızıysa
            önce o servisi kontrol edin.
          </CardHint>
          <p className="card-stat">
            <Pill
              ok={overall}
              label={overall ? "Sistem hazır" : "Eksik veya hatalı bileşen"}
            />
          </p>
          <ul className="check-list">
            <li>
              <span className="check-label">Veritabanı (kullanıcı / accounting)</span>
              <Pill ok={h.postgres} label={h.postgres ? "Çalışıyor" : "Kapalı"} />
            </li>
            <li>
              <span className="check-label">Önbellek (oturum & güvenlik sayaçları)</span>
              <Pill ok={h.redis} label={h.redis ? "Çalışıyor" : "Kapalı"} />
            </li>
          </ul>
          <p className="card-meta">Yazılım sürümü: {data.api_version}</p>
        </div>

        <div className="card">
          <h2 className="card-title">Şu an açık oturumlar</h2>
          <CardHint>
            RADIUS üzerinden &quot;hâlâ bağlı&quot; kabul edilen oturum sayısı (hızlı erişim
            için Redis’te tutulur).
          </CardHint>
          <div className="big-num">{data.sessions.count}</div>
          <p className="card-meta">
            Önbellekte eşleşen kayıt: {data.redis_metrics.nac_acct_keys}
            {data.redis_metrics.nac_acct_keys_truncated ? "+" : ""}
          </p>
          {data.sessions.error && (
            <p className="error">Önbellek okunamadı: {data.sessions.error}</p>
          )}
        </div>

        <div className="card">
          <h2 className="card-title">Kayıtlı kullanıcılar</h2>
          <CardHint>
            RADIUS’ta tanımlı hesap satırları ve grup (VLAN) atamaları.
          </CardHint>
          <div className="big-num">{data.users.radcheck_count}</div>
          <p className="card-meta">Grup / politika satırı: {data.users.radusergroup_count}</p>
          {data.users.error && <p className="error">{data.users.error}</p>}
        </div>

        <div className="card">
          <h2 className="card-title">Bağlantı geçmişi (veritabanı)</h2>
          <CardHint>
            Toplam accounting kaydı ve henüz kapanmamış (Stop gelmemiş) oturum sayısı.
          </CardHint>
          <div className="big-num">{data.accounting.radacct_rows}</div>
          <p className="card-meta">Veritabanında açık görünen: {data.accounting.open_sessions_db}</p>
          {data.accounting.error && <p className="error">{data.accounting.error}</p>}
        </div>

        <div className="card">
          <h2 className="card-title">Başarısız giriş takibi</h2>
          <CardHint>
            Çok fazla yanlış şifre denemesi yapan kullanıcılar için açılmış sayaç sayısı
            (rate limit). Sıfırlamak için Redis anahtarını silmek gerekir.
          </CardHint>
          <div className="big-num">{data.redis_metrics.auth_fail_keys}</div>
          <p className="card-meta">
            {data.redis_metrics.auth_fail_keys_truncated
              ? "En az 500 farklı sayaç (üst sınıra ulaşıldı)"
              : "Aktif sayaç grubu"}
          </p>
        </div>
      </div>

      <section className="panel">
        <SectionTitle
          title="Son bağlantı kayıtları"
          description="En son tamamlanan veya devam eden oturumlar. Tarihler yerel saat diliminize göre gösterilir; veri miktarı indirme / yükleme olarak okunur."
        />
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>
                  Kullanıcı
                  <span className="th-hint">Giriş yapan hesap adı</span>
                </th>
                <th>
                  Erişim noktası
                  <span className="th-hint">Switch / ağ geçidi IP’si (NAS)</span>
                </th>
                <th>
                  Başlangıç
                  <span className="th-hint">Oturumun açıldığı an</span>
                </th>
                <th>
                  Bitiş
                  <span className="th-hint">Kapanış; boşsa sürüyor</span>
                </th>
                <th>
                  Süre
                  <span className="th-hint">Ne kadar süredir açık</span>
                </th>
                <th>
                  İndirilen
                  <span className="th-hint">Cihaza gelen veri (octet = bayt)</span>
                </th>
                <th>
                  Yüklenen
                  <span className="th-hint">Cihazdan çıkan veri</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {data.accounting.recent.length === 0 ? (
                <tr>
                  <td colSpan={7} className="empty-cell">
                    Henüz accounting kaydı yok. RADIUS accounting veya API üzerinden test
                    gönderebilirsiniz.
                  </td>
                </tr>
              ) : (
                data.accounting.recent.map((r, i) => (
                  <tr key={i}>
                    <td className="td-strong">{r.username ?? "—"}</td>
                    <td title={r.nas_ip ?? ""}>{simplifyNas(r.nas_ip)}</td>
                    <td>{formatDateTime(r.acct_start)}</td>
                    <td>{r.acct_stop ? formatDateTime(r.acct_stop) : "Devam ediyor"}</td>
                    <td>{formatDurationSeconds(r.session_time)}</td>
                    <td>{formatDataVolume(r.in_octets)}</td>
                    <td>{formatDataVolume(r.out_octets)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {data.sessions.items.length > 0 && (
        <section className="panel">
          <SectionTitle
            title="Önbellekteki oturumlar"
            description="Şu an Redis’te tutulan kısa özet. Uzun kimliklerin tamamını görmek için satırın üzerine gelin."
          />
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>
                    Benzersiz oturum no
                    <span className="th-hint">
                      Sistem içi tekil ID; aynı kullanıcının iki oturumunu ayırt eder
                    </span>
                  </th>
                  <th>
                    Kullanıcı
                    <span className="th-hint">Bu oturumdaki hesap</span>
                  </th>
                  <th>
                    Erişim noktası
                    <span className="th-hint">NAS IP</span>
                  </th>
                  <th>
                    Oturum etiketi
                    <span className="th-hint">
                      NAS’ın verdiği isim (Session ID); raporlarda sık geçer
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.sessions.items.slice(0, 15).map((s, i) => {
                  const uid = shortenSessionId(s.acct_unique_session_id as string | undefined);
                  return (
                    <tr key={i}>
                      <td className="mono" title={uid.full || undefined}>
                        {uid.short}
                      </td>
                      <td className="td-strong">{(s.username as string) ?? "—"}</td>
                      <td title={(s.nas_ip as string) || ""}>
                        {simplifyNas((s.nas_ip as string) || null)}
                      </td>
                      <td className="mono">{(s.acct_session_id as string) ?? "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="glossary panel" aria-labelledby="glossary-heading">
        <h2 id="glossary-heading" className="section-title">
          Sık sorulan: Bu kısaltmalar ne?
        </h2>
        <p className="section-desc">
          RADIUS ve ağ dokümantasyonunda İngilizce terimler çıkar; burada sade Türkçe karşılıkları
          var.
        </p>
        <dl className="glossary-list">
          <dt>İndirilen / Yüklenen (In / Out octets)</dt>
          <dd>
            <strong>Octet</strong> = 1 bayt. <strong>İndirilen</strong>, cihazınıza gelen (ör. web,
            video) veri; <strong>Yüklenen</strong>, cihazınızdan ağa giden veri. Faturalandırma /
            kotada “kullanılan trafik” buna benzer.
          </dd>
          <dt>Benzersiz oturum no (Session unique id)</dt>
          <dd>
            Sunucunun o <strong>tek bir bağlantı oturumu</strong> için ürettiği benzersiz kod.
            Aynı kullanıcı iki kez bağlansa bile her seferinde farklı olur; kayıtları birbirine
            karıştırmamak için kullanılır.
          </dd>
          <dt>Oturum etiketi (Session ID / Acct-Session-Id)</dt>
          <dd>
            Çoğunlukla <strong>switch veya erişim noktası (NAS)</strong> tarafından verilen kısa
            isim. Raporlarda “hangi bağlantı” sorusuna cevap verir; benzersiz oturum no kadar güçlü
            olmayabilir, ikisi birlikte kullanılır.
          </dd>
          <dt>Erişim noktası (NAS)</dt>
          <dd>
            <strong>Network Access Server</strong>: Kullanıcıyı ağa bağlayan cihaz (ör. 802.1X
            switch, kablosuz kontrolör). IP adresi genelde o cihazı gösterir.
          </dd>
          <dt>Accounting</dt>
          <dd>
            “Kim, ne zaman, ne kadar süre bağlandı, ne kadar veri aktardı?” bilgisinin
            kaydedilmesi. <strong>Start</strong> başlangıç, <strong>Stop</strong> bitiş,
            <strong>Interim</strong> ara güncellemedir.
          </dd>
        </dl>
      </section>

      <footer className="page-footer">
        <p>
          <strong>Son yenileme:</strong> {formatUpdatedAt(data.timestamp)}
        </p>
        <p className="footer-hint">
          Teknik API: <span className="mono">GET /monitoring/snapshot</span> · Arayüz: Next.js
        </p>
      </footer>
    </main>
  );
}
