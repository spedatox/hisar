import { useEffect, useState } from "react";
import * as api from "./api.js";

export default function IaconSettings({ lang, onClose, onSaved, onError }) {
  const tr = lang === "tr";
  const [settings, setSettings] = useState(null);
  const [error, setError] = useState("");
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const load = async () => {
    setError("");
    try { setSettings(await api.getLibrarySettings()); }
    catch (err) { setError(err.message); if (err.status === 401) onError(err); }
  };
  useEffect(() => { let live = true; api.getLibrarySettings().then((value) => { if (live) setSettings(value); })
    .catch((err) => { if (live) { setError(err.message); if (err.status === 401) onError(err); } });
    return () => { live = false; }; }, [onError]);
  const save = async (event) => {
    event.preventDefault(); setBusy(true); setError(""); setSaved(false);
    try {
      const result = await api.saveLibrarySettings({ semantic_enabled: settings.semantic_enabled,
        ocr_enabled: settings.ocr_enabled, ocr_languages: settings.ocr_languages,
        ...(key.trim() ? { embedding_api_key: key.trim() } : {}) });
      setSettings(result); setKey(""); setSaved(true); setError(result.warning || ""); onSaved();
    } catch (err) { setError(err.message); if (err.status === 401) onError(err); }
    finally { setBusy(false); }
  };
  const change = (field, value) => { setSettings((s) => ({ ...s, [field]: value })); setSaved(false); };
  return <main className="iacon-settings">
    <button onClick={onClose}>{tr ? "← Kayıtlara dön" : "← Back to records"}</button>
    <h2>{tr ? "Iacon ayarları" : "Iacon settings"}</h2>
    <p>{tr ? "Arama ve belge okuma seçeneklerini burada yönet. Değişiklikler hemen uygulanır." : "Manage search and document reading here. Changes apply immediately."}</p>
    {error && <div className="iacon-alert" role="alert">{error}<button disabled={busy} onClick={load}>{tr ? "Bağlantıyı yeniden dene" : "Check connection again"}</button></div>}
    {!settings && !error && <p role="status">{tr ? "Dizinleme motoruna bağlanılıyor…" : "Connecting to indexing engine…"}</p>}
    {settings && <form onSubmit={save}>
      <div className="iacon-setting-card"><span className={"iacon-status " + (settings.connected ? "ready_keyword" : "failed")}>
        {settings.connected ? (tr ? "Igor bağlı" : "Igor connected") : (tr ? "Katalog bağlantısı eksik" : "Catalog connection missing")}</span>
        <h3>{tr ? "Dizinleme ne zaman yapılır?" : "When does indexing happen?"}</h3>
        <p>{tr ? "Yükleme veya yeni sürüm eklediğinde otomatik başlar. Yeniden dene hemen bir istek gönderir. Ajanlar yalnızca hazır kaynakları kullanır." : "It starts automatically after an upload or a new edition. Retry indexing sends an immediate request. Agents use editions once their text is ready."}</p>
        <p>{tr ? "Bu pencere açıkken durum otomatik güncellenir. Bağlantı kesilirse belgelerin saklanır; yeniden deneme, başlangıç eşitlemesi ve n8n kurtarması bekleyen işleri devam ettirir." : "Status updates automatically while this window is open. If the connection fails, originals stay saved; retry, startup reconciliation and n8n recovery pick up pending work."}</p>
      </div>
      <div className="iacon-setting-card"><label className="iacon-toggle"><span><strong>{tr ? "Anlamsal arama" : "Semantic search"}</strong>
        <small>{tr ? "Tam sözcük yerine anlama göre ilgili pasajları bul." : "Find relevant passages by meaning, even when the words differ."}</small></span>
        <input type="checkbox" checked={settings.semantic_enabled} onChange={(e) => change("semantic_enabled", e.target.checked)} disabled={busy} /></label>
        <p>{tr ? "Etkinleştirildiğinde belge pasajları embedding sağlayıcısına gönderilir. Sözcük araması kullanılmaya devam eder." : "Enabling this sends document passages to the embedding provider. Keyword search remains available while semantic indexing runs."}</p>
        <label>{tr ? "Embedding API anahtarı" : "Embedding API key"}<input type="password" autoComplete="new-password" value={key}
          onChange={(e) => setKey(e.target.value)} disabled={busy} placeholder={settings.embedding_key_configured ? (tr ? "Anahtar kayıtlı · değiştirmek için yaz" : "Key saved · enter a replacement") : (tr ? "OpenAI API anahtarı" : "OpenAI API key")} /></label>
        <small>{tr ? "Boş bırakırsan kayıtlı anahtar korunur." : "Leave blank to keep the saved key."} · {settings.embedding_model}</small>
      </div>
      <div className="iacon-setting-card"><label className="iacon-toggle"><span><strong>{tr ? "Taranmış belgeleri oku (OCR)" : "Read scanned documents (OCR)"}</strong>
        <small>{tr ? "Görsellerden ve taranmış PDF sayfalarından metin çıkar." : "Extract text from images and scanned PDF pages."}</small></span>
        <input type="checkbox" checked={settings.ocr_enabled} onChange={(e) => change("ocr_enabled", e.target.checked)} disabled={busy || (!settings.ocr_runtime.available && !settings.ocr_enabled)} /></label>
        <p>{settings.ocr_runtime.available ? (tr ? "Yerel OCR hazır. Çıkarılan metin, özgün belgeyi doğrulama uyarısı taşır." : "Local OCR is available. Transcriptions carry a warning to verify the original.") :
          (tr ? "Igor sunucusunda Tesseract veya Poppler eksik. OCR etkinleştirilmeden önce motor ve dil paketleri kurulmalı." : "Tesseract or Poppler is missing on Igor. Install the engine and language packs before enabling OCR.")}</p>
        <label>{tr ? "OCR dilleri" : "OCR languages"}<select value={settings.ocr_languages} disabled={busy || !settings.ocr_runtime.available}
          onChange={(e) => change("ocr_languages", e.target.value)}>
          {[...new Set([settings.ocr_languages, "tur+eng", "eng", "tur"])].map((value) => <option value={value} key={value}>{value === "tur+eng" ? (tr ? "Türkçe + İngilizce" : "Turkish + English") : value === "eng" ? "English" : value === "tur" ? "Türkçe" : value}</option>)}
        </select></label>
      </div>
      <div className="iacon-settings-footer"><span role="status">{saved ? (tr ? "Kaydedildi. Bekleyen dizinleme işleri sıraya alındı." : "Saved. Missing indexing work has been queued.") : ""}</span>
        <button className="primary" disabled={busy}>{busy ? (tr ? "Kaydediliyor…" : "Saving…") : (tr ? "Ayarları kaydet" : "Save settings")}</button></div>
    </form>}
  </main>;
}
