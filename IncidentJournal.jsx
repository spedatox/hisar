import { useEffect, useState } from "react";
import * as api from "./api.js";

const copy = {
  en: {
    title: "Incident Journal", subtitle: "SPEDA operational records across all agents", back: "Document catalog",
    refresh: "Refresh", search: "Find an event, agent, service, or incident ID", severity: "Severity",
    allSeverities: "All severities", critical: "Critical", error: "Error", warning: "Warning", test: "Test",
    scope: "Review status", open: "Needs review", all: "All incidents", reviewed: "Reviewed",
    loading: "Loading incidents…", empty: "No incidents match this view.", pick: "Select an incident to inspect its facts and assessment.",
    repeats: "Occurrences", facts: "Recorded facts",
    assessment: "Model assessment", assess: "Assess incident", available: "An assessment can be requested for this incident.",
    running: "An assessment is in progress.", unavailable: "The model did not return an assessment.",
    interrupted: "The assessment was interrupted.", review: "Mark reviewed", pdf: "Export PDF", copyLink: "Copy incident link",
    copied: "Incident link copied.", history: "Recent occurrences", previous: "Previous", next: "Next",
    noSource: "SPEDA runtime", titleFallback: "Incident", failed: "Could not load the incident journal.",
    exportSelected: "Export selected", exportMatching: "Export all matching", selectPage: "Select page",
    clearSelection: "Clear selection", exporting: "Preparing PDF…", selectForExport: "Select for PDF export",
    diagnostic: "Recorded error", nextCheck: "Next check", stack: "Stack locations",
  },
  tr: {
    title: "Olay Günlüğü", subtitle: "Tüm ajanların SPEDA işletim kayıtları", back: "Belge kataloğu",
    refresh: "Yenile", search: "Olay, ajan, hizmet veya olay kimliği ara", severity: "Önem derecesi",
    allSeverities: "Tüm dereceler", critical: "Kritik", error: "Hata", warning: "Uyarı", test: "Test",
    scope: "İnceleme durumu", open: "İnceleme bekliyor", all: "Tüm olaylar", reviewed: "İncelendi",
    loading: "Olaylar yükleniyor…", empty: "Bu görünüme uyan olay yok.", pick: "Bulguları ve değerlendirmeyi görmek için bir olay seç.",
    repeats: "Tekrar sayısı", facts: "Kaydedilen bulgular",
    assessment: "Model değerlendirmesi", assess: "Olayı değerlendir", available: "Bu olay için değerlendirme istenebilir.",
    running: "Değerlendirme sürüyor.", unavailable: "Model bir değerlendirme döndürmedi.",
    interrupted: "Değerlendirme kesildi.", review: "İncelendi olarak işaretle", pdf: "PDF indir", copyLink: "Olay bağlantısını kopyala",
    copied: "Olay bağlantısı kopyalandı.", history: "Son tekrarlar", previous: "Önceki", next: "Sonraki",
    noSource: "SPEDA çalışma zamanı", titleFallback: "Olay", failed: "Olay günlüğü yüklenemedi.",
    exportSelected: "Seçilenleri indir", exportMatching: "Eşleşenlerin tümünü indir", selectPage: "Sayfayı seç",
    clearSelection: "Seçimi temizle", exporting: "PDF hazırlanıyor…", selectForExport: "PDF için seç",
    diagnostic: "Kaydedilen hata", nextCheck: "Sonraki kontrol", stack: "Çağrı konumları",
  },
};

const humanize = (value) => value?.replaceAll("_", " ");

export default function IncidentJournal({ lang, initialIncident, onClose, onError }) {
  const c = copy[lang] || copy.en;
  const [query, setQuery] = useState("");
  const [severity, setSeverity] = useState("");
  const [showReviewed, setShowReviewed] = useState(Boolean(initialIncident));
  const [offset, setOffset] = useState(0);
  const [reload, setReload] = useState(0);
  const [rows, setRows] = useState([]);
  const [nextOffset, setNextOffset] = useState(null);
  const [selected, setSelected] = useState(initialIncident);
  const [incident, setIncident] = useState(null);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState("");
  const [detailError, setDetailError] = useState("");
  const [working, setWorking] = useState("");
  const [notice, setNotice] = useState("");
  const [exportIds, setExportIds] = useState(() => new Set());
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const date = (value) => new Date(value).toLocaleString(lang === "tr" ? "tr-TR" : "en-GB", {
    dateStyle: "medium", timeStyle: "short",
  });
  const select = (identity) => { setSelected(identity); setDetailError(""); setNotice(""); };
  const toggleExport = (id) => setExportIds((previous) => {
    const next = new Set(previous);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    return next;
  });

  const download = async (selection) => {
    setExporting(true);
    setExportError("");
    try {
      await api.exportIncidents(selection ? { ids: [...exportIds] } : {
        q: query, severity: severity || null, reviewed: showReviewed,
      });
    } catch (error) {
      setExportError(error.message);
      if (error.status === 401) onError(error);
    } finally { setExporting(false); }
  };

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setListError("");
    api.listIncidents({ q: query, severity: severity || undefined, reviewed: showReviewed, offset }, controller.signal)
      .then((result) => { setRows(result.incidents); setNextOffset(result.next_offset); })
      .catch((error) => {
        if (controller.signal.aborted) return;
        setListError(error.message || c.failed);
        if (error.status === 401) onError(error);
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [query, severity, showReviewed, offset, reload, onError, c.failed]);

  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    setDetailError("");
    api.getIncident(selected, controller.signal)
      .then(setIncident)
      .catch((error) => {
        if (controller.signal.aborted) return;
        setDetailError(error.message || c.failed);
        if (error.status === 401) onError(error);
      });
    return () => controller.abort();
  }, [selected, reload, onError, c.failed]);

  const change = async (action, type) => {
    setWorking(type);
    setDetailError("");
    try {
      const result = await action(selected);
      setIncident((previous) => previous?.id === result.id ? result : previous);
      if (type === "review") setReload((value) => value + 1);
    } catch (error) {
      setDetailError(error.message);
      if (error.status === 401) onError(error);
    } finally { setWorking(""); }
  };

  const active = incident?.id === selected ? incident : null;
  return <section className="iacon iacon-journal">
    <header className="iacon-header">
      <div className="iacon-brand"><span className="iacon-optimus-logo" aria-hidden="true" /><div>
        <div className="iacon-kicker">IACON · DAMAGE CONTROL</div><h1>{c.title}</h1><p>{c.subtitle}</p>
      </div></div>
      <div className="iacon-actions"><button onClick={onClose}>{c.back}</button>
        <button onClick={() => setReload((value) => value + 1)}>{c.refresh}</button></div>
    </header>
    <div className="iacon-journal-layout">
      <div className="iacon-catalog">
        <label className="iacon-search"><span aria-hidden="true">⌕</span><input aria-label={c.search}
          maxLength={120} placeholder={c.search} value={query} onChange={(e) => { setOffset(0); setQuery(e.target.value); }} /></label>
        <div className="iacon-journal-filters">
          <label>{c.scope}<select aria-label={c.scope} value={showReviewed ? "all" : "open"} onChange={(e) => {
            setOffset(0);
            setShowReviewed(e.target.value === "all");
            if (e.target.value === "open" && severity === "test") setSeverity("");
          }}>
            <option value="open">{c.open}</option><option value="all">{c.all}</option>
          </select></label>
          <label>{c.severity}<select aria-label={c.severity} value={severity} onChange={(e) => { setOffset(0); setSeverity(e.target.value); }}>
            <option value="">{c.allSeverities}</option>
            {["critical", "error", "warning", ...(showReviewed ? ["test"] : [])].map((name) => <option key={name} value={name}>{c[name]}</option>)}
          </select></label>
        </div>
        <div className="iacon-journal-export">
          <button disabled={loading || !rows.length} onClick={() => setExportIds((previous) =>
            new Set([...previous, ...rows.map((row) => row.id)]))}>{c.selectPage}</button>
          <button disabled={!exportIds.size} onClick={() => setExportIds(new Set())}>{c.clearSelection}</button>
          <button disabled={exporting || !exportIds.size} onClick={() => download(true)}>
            {c.exportSelected} ({exportIds.size})</button>
          <button disabled={exporting || loading || (!rows.length && offset === 0)} onClick={() => download(false)}>
            {c.exportMatching}</button>
        </div>
        {exporting && <p className="iacon-note" role="status">{c.exporting}</p>}
        {exportError && <p className="iacon-alert" role="alert">{exportError}</p>}
        {listError ? <p className="iacon-alert" role="alert">{listError}</p> : loading ?
          <p className="iacon-note" role="status">{c.loading}</p> : !rows.length ?
          <p className="iacon-note">{c.empty}</p> :
          <ul className="iacon-journal-list">{rows.map((row) => <li className="iacon-journal-selectable" key={row.id}>
            <input type="checkbox" aria-label={`${c.selectForExport} ${humanize(row.event)} ${row.id}`}
              checked={exportIds.has(row.id)} onChange={() => toggleExport(row.id)} />
            <button aria-pressed={selected === row.id} onClick={() => select(row.id)}>
              <span className="iacon-journal-row"><strong>{humanize(row.event)}</strong>
                <span className={`iacon-journal-severity ${row.severity}`}>{c[row.severity]}</span></span>
              <small>{row.source || c.noSource} · {date(row.observed_at)} · {c.repeats} {row.occurrences}
                {row.reviewed && ` · ${c.reviewed}`}</small>
              {row.summary && <small>{row.summary}</small>}
            </button>
          </li>)}</ul>}
        {(offset > 0 || nextOffset !== null) && <div className="iacon-pagination">
          <button disabled={loading || offset === 0} onClick={() => setOffset(Math.max(0, offset - 30))}>{c.previous}</button>
          <button disabled={loading || nextOffset === null} onClick={() => setOffset(nextOffset)}>{c.next}</button>
        </div>}
      </div>
      <aside className="iacon-inspector" aria-label={c.facts}>
        {detailError && <p className="iacon-alert" role="alert">{detailError}</p>}
        {!active ? <p className="iacon-note">{selected && !detailError ? c.loading : c.pick}</p> : <>
          <div className="iacon-journal-row"><h2>{humanize(active.facts.event) || c.titleFallback}</h2>
            <span className={`iacon-journal-severity ${active.severity}`}>{c[active.severity]}</span></div>
          {active.facts.summary && <p className="iacon-journal-assessment">{active.facts.summary}</p>}
          {active.facts.diagnostic_message && <><h3>{c.diagnostic}</h3>
            <p className="iacon-journal-assessment">{active.facts.diagnostic_message}</p></>}
          {active.facts.next_check && <><h3>{c.nextCheck}</h3>
            <p className="iacon-journal-assessment">{active.facts.next_check}</p></>}
          <div className="iacon-record-actions">
            <button disabled={active.reviewed || Boolean(working)} onClick={() => change(api.markIncidentReviewed, "review")}>{active.reviewed ? c.reviewed : c.review}</button>
            <a className="iacon-open" href={api.incidentPdfUrl(active.id)}>{c.pdf}</a>
            <button onClick={async () => {
              try {
                const link = new URL(window.location.href);
                link.hash = `incident=${active.id}`;
                await navigator.clipboard.writeText(link.href);
                setNotice(c.copied);
              } catch { setNotice(`${window.location.origin}${window.location.pathname}#incident=${active.id}`); }
            }}>{c.copyLink}</button>
          </div>
          {notice && <p className="iacon-note" role="status">{notice}</p>}
          <h3>{c.assessment}</h3>
          <p className="iacon-journal-assessment">{active.assessment || (working === "assessment" ? c.running : c[active.assessment_state])}</p>
          {active.assessment_state === "available" && <button disabled={Boolean(working)}
            onClick={() => change(api.assessIncident, "assessment")}>{c.assess}</button>}
          <h3>{c.facts}</h3>
          <dl className="iacon-journal-facts">{Object.entries(active.facts).filter(([key, value]) =>
            value != null && !["summary", "next_check", "diagnostic_message", "stack"].includes(key)).map(([key, value]) => <div key={key}>
            <dt>{humanize(key)}</dt><dd>{key.endsWith("_at") ? date(value) : String(value)}</dd>
          </div>)}</dl>
          {active.facts.stack && <details><summary>{c.stack}</summary>
            <pre className="iacon-journal-assessment">{active.facts.stack}</pre></details>}
          {active.recent_occurrences.length > 1 && <><h3>{c.history}</h3><ul className="iacon-journal-list">
            {active.recent_occurrences.map((item) => <li key={item.id}>
              <button aria-pressed={selected === item.id} onClick={() => select(item.id)}>{date(item.observed_at)}</button>
            </li>)}
          </ul></>}
        </>}
      </aside>
    </div>
  </section>;
}
