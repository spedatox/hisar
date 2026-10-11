import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as api from "./api.js";
import IaconSettings from "./IaconSettings.jsx";
import "./iacon.css";

const copy = {
  en: {
    hall: "Hall of Records", subtitle: "Your originals. Every edition. Evidence across every conversation.",
    all: "All records", collections: "Collections", archive: "Archive", new: "Add record", refresh: "Refresh",
    search: "Find a title, collection or institution…", title: "Record", edition: "Edition", status: "Index",
    empty: "The Hall is ready for its first record", hint: "Add a calendar, syllabus, menu or reference. Your agents can consult it in any chat.",
    noMatch: "No records match these filters.", select: "Select a record to inspect its original and editions.",
    original: "Open original", download: "Download", newEdition: "Upload new edition", details: "Edit details",
    restore: "Restore", archiveAction: "Archive record", retry: "Retry indexing", history: "Edition history",
    active: "Active", activate: "Make active", issued: "Issue date", coverage: "Coverage", term: "Term",
    filename: "Original", size: "Size", type: "Type", collection: "Collection", institution: "Institution",
    save: "Save record", cancel: "Cancel", file: "Original file", dates: "Edition dates (optional)",
    datesHint: "Set coverage dates for time-specific references, such as a monthly menu. Upload dates are not evidence of coverage.",
    formats: "PDF, TXT, Markdown, CSV, images, DOCX or XLSX · up to 25 MB",
    honest: "PDF, text, CSV, Word and Excel support cited retrieval. Local OCR is optional; transcriptions carry review warnings.",
    saved: "Record saved", archived: "Record updated", aliases: "Aliases (comma separated)", agents: "Allowed agents (comma separated)",
    agentsHint: "Choose all, selected or no assistants. Execution workers receive no credentials.",
    access: "Agent access", allAgents: "All assistants", selectedAgents: "Selected assistants", noAgents: "No assistants",
    uncategorized: "Unfiled", recordCount: "records", working: "Saving…", previous: "Previous", more: "Next",
    notConfigured: "Originals are stored. Connect Igor to enable indexing.", drop: "Drop one original to add a record",
    pending: "Queued", processing: "Indexing", ready_keyword: "Keyword ready", needs_review: "Needs review",
    ready_ocr: "OCR · verify original",
    failed: "Index failed", no_edition: "No edition", withdrawn: "Withdrawn", archivedState: "Archived",
    reviewHint: "This edition needs extraction review. Its original remains available; it is not used as answer evidence.",
    pendingHint: "Indexing starts after upload. Status updates automatically here; retry sends an immediate request if work is stuck.",
    readyHint: "This edition is available to authorized agents through cited keyword retrieval.",
    ocrHint: "This edition includes OCR transcription. Agents can cite it with a review warning; verify details against the original.",
    reference: "Reference", academic_calendar: "Academic calendar", syllabus: "Syllabus", transcript: "Transcript",
    cafeteria_menu: "Cafeteria menu", book: "Book", confirmArchive: "Archive this record? Its originals and editions will be retained.",
  },
  tr: {
    hall: "Kayıtlar Salonu", subtitle: "Özgün belgelerin. Her sürüm. Her sohbette erişilebilir kanıt.",
    all: "Tüm kayıtlar", collections: "Koleksiyonlar", archive: "Arşiv", new: "Kayıt ekle", refresh: "Yenile",
    search: "Başlık, koleksiyon veya kurum ara…", title: "Kayıt", edition: "Sürüm", status: "Dizin",
    empty: "Salon ilk kaydını bekliyor", hint: "Takvim, ders izlencesi, menü veya kaynak ekle. Ajanların her sohbette başvurabilsin.",
    noMatch: "Bu filtrelerle eşleşen kayıt yok.", select: "Özgün belgeyi ve sürümlerini incelemek için bir kayıt seç.",
    original: "Özgün belgeyi aç", download: "İndir", newEdition: "Yeni sürüm yükle", details: "Bilgileri düzenle",
    restore: "Geri getir", archiveAction: "Kaydı arşivle", retry: "Dizinlemeyi yeniden dene", history: "Sürüm geçmişi",
    active: "Etkin", activate: "Etkinleştir", issued: "Yayın tarihi", coverage: "Kapsam", term: "Dönem",
    filename: "Özgün dosya", size: "Boyut", type: "Tür", collection: "Koleksiyon", institution: "Kurum",
    save: "Kaydı kaydet", cancel: "İptal", file: "Özgün dosya", dates: "Sürüm tarihleri (isteğe bağlı)",
    datesHint: "Aylık menü gibi tarihli kaynaklara kapsam tarihi ekle. Yükleme tarihi kapsamı kanıtlamaz.",
    formats: "PDF, TXT, Markdown, CSV, görsel, DOCX veya XLSX · en fazla 25 MB",
    honest: "PDF, metin, CSV, Word ve Excel kaynaklı aramayı destekler. Yerel OCR isteğe bağlıdır; çıkarımlar doğrulama uyarısı taşır.",
    saved: "Kayıt kaydedildi", archived: "Kayıt güncellendi", aliases: "Diğer adlar (virgülle ayır)", agents: "İzinli ajanlar (virgülle ayır)",
    agentsHint: "Tüm, seçilen veya hiçbir asistana izin ver. İşçi ajanlara erişim anahtarı verilmez.",
    access: "Ajan erişimi", allAgents: "Tüm asistanlar", selectedAgents: "Seçilen asistanlar", noAgents: "Hiçbir asistan",
    uncategorized: "Koleksiyonsuz", recordCount: "kayıt", working: "Kaydediliyor…", previous: "Önceki", more: "Sonraki",
    notConfigured: "Özgün belgeler saklandı. Dizinleme için Igor bağlantısını yapılandır.", drop: "Kayıt eklemek için bir özgün dosya bırak",
    pending: "Sırada", processing: "Dizinleniyor", ready_keyword: "Sözcük araması hazır", needs_review: "İnceleme gerekli",
    ready_ocr: "OCR · özgünü doğrula",
    failed: "Dizinleme başarısız", no_edition: "Sürüm yok", withdrawn: "Geri çekildi", archivedState: "Arşivlendi",
    reviewHint: "Bu sürümün çıkarımı inceleme gerektiriyor. Özgün belge açılabilir; yanıt kanıtı olarak kullanılmaz.",
    pendingHint: "Dizinleme yüklemeden sonra başlar. Durum burada otomatik güncellenir; iş takılırsa yeniden dene hemen bir istek gönderir.",
    readyHint: "Bu sürüm, izinli ajanlar tarafından kaynaklı sözcük aramasıyla kullanılabilir.",
    ocrHint: "Bu sürüm OCR çıkarımı içerir. Ajanlar doğrulama uyarısıyla kaynak gösterebilir; ayrıntıları özgün belgede doğrula.",
    reference: "Kaynak", academic_calendar: "Akademik takvim", syllabus: "Ders izlencesi", transcript: "Transkript",
    cafeteria_menu: "Yemekhane menüsü", book: "Kitap", confirmArchive: "Kayıt arşivlensin mi? Özgün belgeler ve sürümler korunacak.",
  },
};

const types = ["reference", "academic_calendar", "syllabus", "transcript", "cafeteria_menu", "book"];
const csv = (value) => (value || "").split(",").map((s) => s.trim()).filter(Boolean);
const blank = { title: "", category: "", doc_type: "reference", institution: "", aliases: "", agents: "", access_mode: "all",
                issue_date: "", coverage_start: "", coverage_end: "", term: "" };

export default function HallOfRecords({ lang = "en", onError, notify }) {
  const c = copy[lang] || copy.en;
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [collection, setCollection] = useState(null);
  const [archived, setArchived] = useState(false);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(null);
  const [editions, setEditions] = useState([]);
  const [editing, setEditing] = useState(null);
  const [draft, setDraft] = useState(blank);
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [page, setPage] = useState(0);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [indexing, setIndexing] = useState({});
  const [engineError, setEngineError] = useState("");
  const [retrying, setRetrying] = useState(null);
  const formRef = useRef(null);
  const uploadRef = useRef(null);
  const requestRef = useRef(0);

  const reload = useCallback(async (reconcile = false) => {
    const request = ++requestRef.current;
    setLoading(true); setError("");
    try {
      if (reconcile) {
        try {
          const result = await api.refreshLibrary();
          if (result.status === "unconfigured") setError(c.notConfigured);
        } catch (err) { if (err.status === 401) throw err; setError(err.message); }
      }
      const rows = [];
      let offset = 0;
      do {
        const data = await api.listLibrary(true, offset);
        rows.push(...data.records);
        if (!data.has_more) break;
        offset = data.next_offset;
      } while (true);
      if (request === requestRef.current) setRecords(rows);
    } catch (err) {
      if (request === requestRef.current) { setError(err.message); onError(err); }
    } finally { if (request === requestRef.current) setLoading(false); }
  }, [c.notConfigured, onError]);

  useEffect(() => { reload(); return () => { requestRef.current++; }; }, [reload]);
  useEffect(() => () => uploadRef.current?.abort(), []);
  const record = records.find((r) => r.document.id === selected);
  const documentIds = records.filter((r) => !r.document.is_archived && r.active_revision).map((r) => r.document.id).join(",");
  useEffect(() => {
    let live = true, timer;
    const poll = async () => {
      try {
        if (document.visibilityState !== "hidden" && documentIds) {
          const ids = documentIds.split(","), rows = [];
          for (let offset = 0; offset < ids.length; offset += 100) {
            const result = await api.getLibraryProgress(ids.slice(offset, offset + 100));
            rows.push(...result.records);
          }
          if (live) { setIndexing(Object.fromEntries(rows.map((row) => [row.document_id, row]))); setEngineError(""); }
        }
      } catch (err) { if (live) { setEngineError(err.message); if (err.status === 401) onError(err); } }
      finally { if (live) timer = setTimeout(poll, 3000); }
    };
    poll();
    return () => { live = false; clearTimeout(timer); };
  }, [documentIds, onError]);
  const liveStatus = (r) => {
    const value = indexing[r.document.id];
    return value && (value.state === "not_synced" || value.revision_id === r.active_revision?.id) ? value : null;
  };
  const retry = async () => {
    setRetrying(selected); setError("");
    try {
      await api.retryLibraryIndex(selected);
      notify(lang === "tr" ? "Yeniden deneme kabul edildi. Dizinleme durumu otomatik güncellenir." : "Retry accepted. Indexing status updates automatically.");
      const result = await api.getLibraryProgress([selected]);
      setIndexing((before) => ({ ...before, ...Object.fromEntries(result.records.map((row) => [row.document_id, row])) }));
      await reload();
    } catch (err) { setError(err.message); if (err.status === 401) onError(err); }
    finally { setRetrying(null); }
  };
  const indexingView = (r) => {
    const info = liveStatus(r);
    if (!info) return null;
    const p = info.progress || {}, running = ["pending", "processing", "retry_wait", "not_synced"].includes(info.state);
    const names = lang === "tr" ? { queued: "Sırada", downloading: "Özgün belge indiriliyor", extracting: "Metin çıkarılıyor", ocr: "Taranmış sayfa okunuyor", publishing: "Pasajlar kaydediliyor", embedding: "Anlamsal arama hazırlanıyor", ready: "Dizinleme tamamlandı", retry_wait: "Yeniden deneme bekleniyor", awaiting_sync: "Igor ile eşitleme bekleniyor", failed: "Dizinleme başarısız", needs_review: "İnceleme gerekli" } :
      { queued: "Queued", downloading: "Downloading original", extracting: "Extracting text", ocr: "Reading scanned page", publishing: "Saving passages", embedding: "Preparing semantic search", ready: "Indexing complete", retry_wait: "Waiting to retry", awaiting_sync: "Awaiting Igor sync", failed: "Indexing failed", needs_review: "Needs review" };
    return <div className="iacon-index-progress" role="status"><strong>{names[p.stage] || stateLabel(info.state)}</strong>
      {running && <progress aria-label={names[p.stage] || c.processing} max={p.total || undefined} value={p.total ? p.completed || 0 : undefined} />}
      {p.total > 0 && <small>{p.completed || 0} / {p.total} {p.unit === "pages" ? (lang === "tr" ? "sayfa" : "pages") : (lang === "tr" ? "pasaj" : "passages")}</small>}
      {info.semantic?.enabled && <small>{lang === "tr" ? "Anlamsal arama" : "Semantic search"}: {info.semantic.indexed} / {info.semantic.total} {lang === "tr" ? "pasaj hazır" : "passages ready"}</small>}
      {info.message && <p>{info.message}</p>}
      {info.retry_after && <small>{lang === "tr" ? "Bir sonraki kurtarma için uygun:" : "Eligible for next recovery:"} {new Date(info.retry_after).toLocaleTimeString()} · {lang === "tr" ? "Yeniden dene şimdi başlatır" : "Retry starts it now"}</small>}
    </div>;
  };
  useEffect(() => {
    let live = true;
    setEditions([]);
    if (selected) api.listLibraryRevisions(selected).then((rows) => { if (live) setEditions(rows); })
      .catch((err) => { if (live) onError(err); });
    return () => { live = false; };
  }, [selected, record?.document.metadata_version, onError]);
  useEffect(() => {
    if (!editing) return;
    const before = document.activeElement;
    formRef.current?.querySelector("input")?.focus();
    const keyboard = (event) => {
      if (event.key === "Escape" && !busy) setEditing(null);
      if (event.key === "Tab") {
        const controls = [...(formRef.current?.querySelectorAll("button:not(:disabled),input,select") || [])];
        const first = controls[0], last = controls[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    };
    document.addEventListener("keydown", keyboard);
    return () => { document.removeEventListener("keydown", keyboard); before?.focus(); };
  }, [editing, busy]);

  const collections = useMemo(() => [...new Set(records.filter((r) => !r.document.is_archived)
    .map((r) => r.document.category).filter(Boolean))].sort(), [records]);
  const visible = useMemo(() => records.filter(({ document: d }) =>
    d.is_archived === archived && (collection === null || d.category === collection) &&
    [d.title, d.category, d.institution, ...(d.aliases || [])].some((value) =>
      (value || "").toLocaleLowerCase(lang).includes(query.toLocaleLowerCase(lang)))),
  [records, archived, collection, query, lang]);
  useEffect(() => { setPage(0); }, [archived, collection, query]);

  const start = (mode, incoming = null) => {
    const d = record?.document;
    const rev = record?.active_revision;
    setDraft(mode === "new" ? { ...blank, category: collection || "", title: incoming?.name.replace(/\.[^.]+$/, "") || "" } : {
      ...blank, title: d.title, category: d.category || "", doc_type: d.type || "reference",
      institution: d.institution || "", aliases: (d.aliases || []).join(", "),
      agents: (d.access_policy?.allowed_agents || []).join(", "),
      access_mode: d.access_policy?.allowed_agents == null ? "all" : d.access_policy.allowed_agents.length ? "selected" : "none",
      ...(mode === "edit" ? {} : { issue_date: "", coverage_start: "", coverage_end: "", term: rev?.term || "" }),
    });
    setDraft((values) => ({ ...values, expected_version: d?.metadata_version }));
    setFile(incoming); setEditing(mode); setProgress(null);
  };
  const change = (key) => (event) => setDraft((d) => ({ ...d, [key]: event.target.value }));
  const action = async (fn) => {
    setBusy(true);
    try { await fn(); await reload(); notify(c.archived); }
    catch (err) { onError(err); }
    finally { setBusy(false); }
  };
  const submit = async (event) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    try {
      if (editing === "edit") {
        await api.updateLibraryDocument(selected, { expected_version: draft.expected_version,
          title: draft.title, category: draft.category || null, type: draft.doc_type,
          institution: draft.institution || null, aliases: csv(draft.aliases),
          access_policy: draft.access_mode === "all" ? {} : { allowed_agents: draft.access_mode === "none" ? [] : csv(draft.agents) } });
      } else {
        if (!file) throw new Error(c.file);
        const metadata = { issue_date: draft.issue_date, coverage_start: draft.coverage_start,
          coverage_end: draft.coverage_end, term: draft.term,
          onProgress: (loaded, total) => setProgress(Math.round(loaded / total * 100)) };
        const task = editing === "new"
          ? api.uploadLibraryRecord(file, { ...metadata, title: draft.title, category: draft.category, doc_type: draft.doc_type })
          : api.uploadLibraryRevision(selected, file, { ...metadata, expected_version: draft.expected_version });
        uploadRef.current = task;
        const result = await task;
        if (editing === "new") setSelected(result.document.id);
      }
      setEditing(null); await reload(); notify(c.saved);
    } catch (err) { onError(err); }
    finally { uploadRef.current = null; setBusy(false); setProgress(null); }
  };
  const stateLabel = (state) => state === "archived" ? c.archivedState : state === "not_synced" ? (lang === "tr" ? "Eşitleme bekliyor" : "Awaiting sync") : state === "retry_wait" ? (lang === "tr" ? "Yeniden deneme bekliyor" : "Waiting to retry") : c[state] || state;
  const counts = { active: records.filter((r) => !r.document.is_archived).length };

  return <div className="iacon" onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
    onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setDragging(false); }}
    onDrop={(e) => { e.preventDefault(); setDragging(false); if (!busy && !editing && e.dataTransfer.files[0]) start("new", e.dataTransfer.files[0]); }}>
    <header className="iacon-header"><div className="iacon-brand"><span className="iacon-optimus-logo" aria-hidden="true" /><div><div className="iacon-kicker">IACON</div><h1>{c.hall}</h1><p>{c.subtitle}</p></div></div>
      <div className="iacon-actions"><button onClick={() => setSettingsOpen((open) => !open)}>{lang === "tr" ? "Ayarlar" : "Settings"}</button><button disabled={loading || busy} onClick={() => reload(true)}>{c.refresh}</button>
        <button className="primary" disabled={busy} onClick={() => start("new")}>+ {c.new}</button></div></header>
    {(error || engineError) && <div className="iacon-alert" role="alert">{error || engineError}</div>}
    {settingsOpen ? <IaconSettings lang={lang} onClose={() => setSettingsOpen(false)} onSaved={() => reload()} onError={onError} /> : <div className="iacon-layout">
      <nav className="iacon-collections" aria-label={c.collections}>
        <div className="iacon-count">{counts.active}<small>{c.recordCount}</small></div>
        <button className={!archived && collection === null ? "selected" : ""} onClick={() => { setArchived(false); setCollection(null); }}>{c.all}<span>{counts.active}</span></button>
        <h2>{c.collections}</h2>
        {collections.map((name) => <button key={name} className={!archived && collection === name ? "selected" : ""}
          onClick={() => { setArchived(false); setCollection(name); }}>{name}</button>)}
        <button className={archived ? "selected" : ""} onClick={() => { setArchived(true); setCollection(null); }}>{c.archive}<span>{records.filter((r) => r.document.is_archived).length}</span></button>
        <p className="iacon-note">{c.honest}</p>
      </nav>
      <main className="iacon-catalog">
        <label className="iacon-search"><span aria-hidden="true">⌕</span><input aria-label={c.search} placeholder={c.search} value={query} onChange={(e) => setQuery(e.target.value)} /></label>
        {loading && records.length === 0 ? <div className="iacon-empty" role="status">…</div> : visible.length === 0 ?
          <div className="iacon-empty"><div className="iacon-empty-symbol" aria-hidden="true">▤</div><h2>{query || collection || archived ? c.noMatch : c.empty}</h2>
            {!query && !collection && !archived && <><p>{c.hint}</p><button className="primary" onClick={() => start("new")}>+ {c.new}</button></>}</div> :
          <><div className="iacon-table"><table><thead><tr><th>{c.title}</th><th>{c.edition}</th><th>{c.status}</th></tr></thead>
            <tbody>{visible.slice(page * 30, page * 30 + 30).map((r) => <tr key={r.document.id} className={selected === r.document.id ? "selected" : ""}>
              <td><button className="iacon-record-title" onClick={() => setSelected(r.document.id)}><span className="iacon-filemark" aria-hidden="true">▤</span>
                <span><strong>{r.document.title}</strong><small>{c[r.document.type] || r.document.type || c.reference} · {r.document.category || c.uncategorized}</small></span></button></td>
              <td><span className="iacon-edition">{r.active_revision ? String(r.active_revision.sequence).padStart(2, "0") : "—"}</span><small>{r.active_revision?.issue_date || "—"}</small></td>
              <td><span className={"iacon-status " + (liveStatus(r)?.state || r.index_status)}>{stateLabel(liveStatus(r)?.state || r.index_status)}</span>
                {["pending", "processing", "retry_wait"].includes(liveStatus(r)?.state) && indexingView(r)}</td>
            </tr>)}</tbody></table></div>
            {visible.length > 30 && <div className="iacon-pagination"><button disabled={page === 0} onClick={() => setPage((v) => v - 1)}>{c.previous}</button><span>{page + 1} / {Math.ceil(visible.length / 30)}</span>
              <button disabled={(page + 1) * 30 >= visible.length} onClick={() => setPage((v) => v + 1)}>{c.more}</button></div>}</>}
      </main>
      <aside className="iacon-inspector">
        {!record ? <p className="iacon-note">{c.select}</p> : <>
          <div className="iacon-kicker">{c.title}</div><h2>{record.document.title}</h2>
          <span className={"iacon-status " + (liveStatus(record)?.state || record.index_status)}>{stateLabel(liveStatus(record)?.state || record.index_status)}</span>
          {indexingView(record)}
          <p className="iacon-note">{record.index_status === "ready_keyword" ? c.readyHint : record.index_status === "ready_ocr" ? c.ocrHint : record.index_status === "needs_review" ? c.reviewHint : c.pendingHint}</p>
          {record.active_revision && <><a className="iacon-open" href={api.downloadLibraryRevisionUrl(record.active_revision.id, true)} target="_blank" rel="noopener noreferrer">{c.original} ↗</a>
            <dl><dt>{c.filename}</dt><dd>{record.active_revision.original_filename}</dd><dt>{c.size}</dt><dd>{api.fmtBytes(record.active_revision.size_bytes)}</dd>
              <dt>{c.issued}</dt><dd>{record.active_revision.issue_date || "—"}</dd><dt>{c.coverage}</dt><dd>{record.active_revision.coverage_start ? record.active_revision.coverage_start + " → " + record.active_revision.coverage_end : "—"}</dd>
              <dt>{c.term}</dt><dd>{record.active_revision.term || "—"}</dd></dl></>}
          <div className="iacon-record-actions"><button disabled={busy || record.document.is_archived} onClick={() => start("edition")}>{c.newEdition}</button>
            <button disabled={busy} onClick={() => start("edit")}>{c.details}</button>
            <button disabled={busy || retrying === selected || liveStatus(record)?.state === "processing" || !record.active_revision || record.document.is_archived} onClick={retry}>{retrying === selected ? (lang === "tr" ? "İstek gönderiliyor…" : "Sending request…") : c.retry}</button>
            <button disabled={busy} onClick={() => {
              if (record.document.is_archived || window.confirm(c.confirmArchive)) action(() => api.updateLibraryDocument(selected,
                { expected_version: record.document.metadata_version, is_archived: !record.document.is_archived }));
            }}>{record.document.is_archived ? c.restore : c.archiveAction}</button></div>
          <h3>{c.history}</h3>
          <ol className="iacon-history">{editions.map((rev) => <li key={rev.id}><div><strong>{c.edition} {String(rev.sequence).padStart(2, "0")}</strong>
            {rev.id === record.document.active_revision_id && <span>{c.active}</span>}</div><small>{rev.issue_date || new Date(rev.created_at).toLocaleDateString(lang === "tr" ? "tr-TR" : "en-US")}</small>
            <div><a href={api.downloadLibraryRevisionUrl(rev.id)}>{c.download}</a>{rev.id !== record.document.active_revision_id && <button disabled={busy}
              onClick={() => action(() => api.updateLibraryDocument(selected, { expected_version: record.document.metadata_version, active_revision_id: rev.id }))}>{c.activate}</button>}</div></li>)}</ol>
        </>}
      </aside>
    </div>}
    {dragging && <div className="iacon-drop" aria-hidden="true">{c.drop}</div>}
    {editing && <div className="iacon-modal"><form ref={formRef} onSubmit={submit} role="dialog" aria-modal="true" aria-labelledby="iacon-form-title">
      <div className="iacon-kicker">I A C O N</div><h2 id="iacon-form-title">{editing === "new" ? c.new : editing === "edit" ? c.details : c.newEdition}</h2>
      {editing !== "edition" && <><label>{c.title}<input required maxLength={240} value={draft.title} onChange={change("title")} /></label>
        <div className="iacon-form-row"><label>{c.collection}<input maxLength={200} list="iacon-collection-options" value={draft.category} onChange={change("category")} /></label>
          <label>{c.type}<select value={draft.doc_type} onChange={change("doc_type")}>{types.map((type) => <option key={type} value={type}>{c[type]}</option>)}</select></label></div></>}
      <datalist id="iacon-collection-options">{collections.map((name) => <option key={name} value={name} />)}</datalist>
      {editing === "edit" ? <><label>{c.institution}<input maxLength={240} value={draft.institution} onChange={change("institution")} /></label>
        <label>{c.aliases}<input value={draft.aliases} onChange={change("aliases")} /></label>
        <label>{c.access}<select value={draft.access_mode} onChange={change("access_mode")}>
          <option value="all">{c.allAgents}</option><option value="selected">{c.selectedAgents}</option><option value="none">{c.noAgents}</option>
        </select></label>
        {draft.access_mode === "selected" && <label>{c.agents}<input required value={draft.agents} onChange={change("agents")} /></label>}
        <p className="iacon-note">{c.agentsHint}</p></> :
        <><label>{c.file}<input required={!file} type="file" accept=".pdf,.txt,.md,.csv,.png,.jpg,.jpeg,.docx,.xlsx" onChange={(e) => setFile(e.target.files[0] || null)} aria-required={!file} />
          {file && <small>{file.name} · {api.fmtBytes(file.size)}</small>}</label><p className="iacon-note">{c.formats}</p>
          <fieldset><legend>{c.dates}</legend><div className="iacon-form-row"><label>{c.issued}<input type="date" value={draft.issue_date} onChange={change("issue_date")} /></label>
            <label>{c.term}<input maxLength={100} value={draft.term} onChange={change("term")} /></label></div>
            <div className="iacon-form-row"><label>{c.coverage} — {lang === "tr" ? "başlangıç" : "start"}<input type="date" required={!!draft.coverage_end} value={draft.coverage_start} onChange={change("coverage_start")} /></label>
              <label>{c.coverage} — {lang === "tr" ? "bitiş" : "end"}<input type="date" required={!!draft.coverage_start} min={draft.coverage_start || undefined} value={draft.coverage_end} onChange={change("coverage_end")} /></label></div>
            <p className="iacon-note">{c.datesHint}</p></fieldset></>}
      {progress !== null && <progress value={progress} max={100} aria-label={c.working} />}
      <div className="iacon-actions"><button type="button" disabled={busy} onClick={() => setEditing(null)}>{c.cancel}</button>
        <button className="primary" disabled={busy || (editing !== "edit" && !file)}>{busy ? c.working : c.save}</button></div>
    </form></div>}
  </div>;
}
