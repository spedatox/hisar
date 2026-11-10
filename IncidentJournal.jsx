import { useEffect, useRef, useState } from "react";
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
    bulkActions: "Bulk actions", selectedRows: (n) => `Selected incidents (${n})`, matching: "All matching incidents",
    selectPage: "Select page", clearSelection: "Clear selection", selectIncident: "Select incident",
    unreview: "Mark unreviewed", assessBatch: (n) => `Assess up to ${n}`, copyLinks: "Copy links",
    working: "Working…", exporting: "Preparing PDF…", exported: "PDF downloaded.",
    reviewedCount: (changed, matched, reviewed) => `${changed} of ${matched} incidents marked ${reviewed ? "reviewed" : "unreviewed"}.`,
    assessmentProgress: (done, total) => `Assessing incidents (${done}/${total})…`,
    assessedCount: (complete, total, left) => `${complete} of ${total} assessments completed.${left ? ` ${left} eligible for the next batch.` : ""}`,
    noneToAssess: "No incidents in this scope are available for assessment.",
    copiedCount: (n) => `${n} incident links copied.`, manualCopy: "Incident links to copy",
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
    bulkActions: "Toplu işlemler", selectedRows: (n) => `Seçilen olaylar (${n})`, matching: "Eşleşen tüm olaylar",
    selectPage: "Sayfayı seç", clearSelection: "Seçimi temizle", selectIncident: "Olayı seç",
    unreview: "İncelenmedi olarak işaretle", assessBatch: (n) => `En fazla ${n} olayı değerlendir`, copyLinks: "Bağlantıları kopyala",
    working: "İşlem sürüyor…", exporting: "PDF hazırlanıyor…", exported: "PDF indirildi.",
    reviewedCount: (changed, matched, reviewed) => `${matched} olaydan ${changed} tanesi ${reviewed ? "incelendi" : "incelenmedi"} olarak işaretlendi.`,
    assessmentProgress: (done, total) => `Olaylar değerlendiriliyor (${done}/${total})…`,
    assessedCount: (complete, total, left) => `${total} değerlendirmeden ${complete} tanesi tamamlandı.${left ? ` Sonraki grup için ${left} olay uygun.` : ""}`,
    noneToAssess: "Bu kapsamdaki hiçbir olay değerlendirmeye uygun değil.",
    copiedCount: (n) => `${n} olay bağlantısı kopyalandı.`, manualCopy: "Kopyalanacak olay bağlantıları",
    diagnostic: "Kaydedilen hata", nextCheck: "Sonraki kontrol", stack: "Çağrı konumları",
  },
};

const humanize = (value) => value?.replaceAll("_", " ");
const assessmentBatchSize = 10;

function incidentLink(id) {
  const link = new URL(window.location.href);
  link.hash = `incident=${id}`;
  return link.href;
}

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
  const [checkedIds, setCheckedIds] = useState(() => new Set());
  const [bulkScope, setBulkScope] = useState("selected");
  const [bulkWorking, setBulkWorking] = useState(false);
  const [bulkStatus, setBulkStatus] = useState("");
  const [bulkError, setBulkError] = useState("");
  const [bulkLinks, setBulkLinks] = useState("");
  const mounted = useRef(false);
  const date = (value) => new Date(value).toLocaleString(lang === "tr" ? "tr-TR" : "en-GB", {
    dateStyle: "medium", timeStyle: "short",
  });
  const select = (identity) => { setSelected(identity); setDetailError(""); setNotice(""); };
  const toggleChecked = (id) => setCheckedIds((previous) => {
    const next = new Set(previous);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    return next;
  });

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  const runBulk = async (action) => {
    const scope = bulkScope === "selected" ? { ids: [...checkedIds] } : {
      q: query, severity: severity || null, reviewed: showReviewed,
    };
    setBulkWorking(true);
    setBulkError("");
    setBulkLinks("");
    setBulkStatus(action === "pdf" ? c.exporting : c.working);
    try {
      if (action === "pdf") {
        await api.exportIncidents(scope);
        setBulkStatus(c.exported);
      } else if (action === "review" || action === "unreview") {
        const markReviewed = action === "review";
        const { matched, changed } = await api.reviewIncidents({ ...scope, mark_reviewed: markReviewed });
        setBulkStatus(c.reviewedCount(changed, matched, markReviewed));
        setOffset(0);
        setReload((value) => value + 1);
      } else {
        const { incidents } = await api.selectIncidents(scope);
        if (action === "copy") {
          if (!incidents.length) {
            setBulkStatus(c.empty);
            return;
          }
          const links = incidents.map(({ id }) => incidentLink(id)).join("\n");
          try {
            await navigator.clipboard.writeText(links);
            setBulkStatus(c.copiedCount(incidents.length));
          } catch {
            setBulkStatus("");
            setBulkLinks(links);
          }
        } else {
          const eligible = incidents.filter((item) => item.assessment_state === "available");
          const batch = eligible.slice(0, assessmentBatchSize);
          if (!batch.length) {
            setBulkStatus(c.noneToAssess);
            return;
          }
          let complete = 0;
          setBulkStatus(c.assessmentProgress(0, batch.length));
          for (const [index, { id }] of batch.entries()) {
            if (!mounted.current) return;
            const result = await api.assessIncident(id);
            if (result.assessment_state === "complete") complete += 1;
            setIncident((previous) => previous?.id === id ? result : previous);
            setBulkStatus(c.assessmentProgress(index + 1, batch.length));
          }
          setBulkStatus(c.assessedCount(complete, batch.length, eligible.length - batch.length));
        }
      }
    } catch (error) {
      setBulkStatus("");
      setBulkError(error.message);
      if (error.status === 401) onError(error);
    } finally { setBulkWorking(false); }
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
  const bulkDisabled = bulkWorking || Boolean(working) ||
    (bulkScope === "selected" ? !checkedIds.size : loading || Boolean(listError) || (!rows.length && offset === 0));
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
        <div className="iacon-journal-bulk">
          <button disabled={bulkWorking || loading || !rows.length} onClick={() => setCheckedIds((previous) =>
            new Set([...previous, ...rows.map((row) => row.id)]))}>{c.selectPage}</button>
          <button disabled={bulkWorking || !checkedIds.size} onClick={() => setCheckedIds(new Set())}>{c.clearSelection}</button>
        </div>
        <div className="iacon-journal-filters">
          <label>{c.bulkActions}<select aria-label={c.bulkActions} disabled={bulkWorking}
            value={bulkScope} onChange={(e) => setBulkScope(e.target.value)}>
            <option value="selected">{c.selectedRows(checkedIds.size)}</option><option value="matching">{c.matching}</option>
          </select></label>
        </div>
        <div className="iacon-journal-bulk">
          <button disabled={bulkDisabled} onClick={() => runBulk("review")}>{c.review}</button>
          <button disabled={bulkDisabled || (bulkScope === "matching" && !showReviewed)}
            onClick={() => runBulk("unreview")}>{c.unreview}</button>
          <button disabled={bulkDisabled} onClick={() => runBulk("assessment")}>{c.assessBatch(assessmentBatchSize)}</button>
          <button disabled={bulkDisabled} onClick={() => runBulk("pdf")}>{c.pdf}</button>
          <button disabled={bulkDisabled} onClick={() => runBulk("copy")}>{c.copyLinks}</button>
        </div>
        {bulkStatus && <p className="iacon-note" role="status">{bulkStatus}</p>}
        {bulkError && <p className="iacon-alert" role="alert">{bulkError}</p>}
        {bulkLinks && <textarea className="iacon-journal-links" readOnly aria-label={c.manualCopy} value={bulkLinks}
          onFocus={(event) => event.target.select()} />}
        {listError ? <p className="iacon-alert" role="alert">{listError}</p> : loading ?
          <p className="iacon-note" role="status">{c.loading}</p> : !rows.length ?
          <p className="iacon-note">{c.empty}</p> :
          <ul className="iacon-journal-list">{rows.map((row) => <li className="iacon-journal-selectable" key={row.id}>
            <input type="checkbox" aria-label={`${c.selectIncident} ${humanize(row.event)} ${row.id}`}
              checked={checkedIds.has(row.id)} disabled={bulkWorking} onChange={() => toggleChecked(row.id)} />
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
            <button disabled={active.reviewed || Boolean(working) || bulkWorking}
              onClick={() => change(api.markIncidentReviewed, "review")}>{active.reviewed ? c.reviewed : c.review}</button>
            <a className="iacon-open" href={api.incidentPdfUrl(active.id)}>{c.pdf}</a>
            <button onClick={async () => {
              try {
                await navigator.clipboard.writeText(incidentLink(active.id));
                setNotice(c.copied);
              } catch { setNotice(incidentLink(active.id)); }
            }}>{c.copyLink}</button>
          </div>
          {notice && <p className="iacon-note" role="status">{notice}</p>}
          <h3>{c.assessment}</h3>
          <p className="iacon-journal-assessment">{active.assessment || (working === "assessment" ? c.running : c[active.assessment_state])}</p>
          {active.assessment_state === "available" && <button disabled={Boolean(working) || bulkWorking}
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
