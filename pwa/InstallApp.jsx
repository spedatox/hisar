import { createContext, useContext, useEffect, useRef, useState } from "react";
import "./install.css";

const InstallAppContext = createContext(null);

function manualInstallKey() {
  const { userAgent, maxTouchPoints } = navigator;
  const mac = /Macintosh/.test(userAgent);
  if (/iPhone|iPad|iPod/.test(userAgent) || (mac && maxTouchPoints > 1)) return "install_ios";
  if (mac && /Version\/[\d.]+.*Safari\//.test(userAgent)) return "install_mac";
  return null;
}

export function InstallAppProvider({ t, children }) {
  const [prompt, setPrompt] = useState(null);
  const [installed, setInstalled] = useState(() =>
    window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true
  );
  const dialog = useRef(null);
  const manualKey = manualInstallKey();

  useEffect(() => {
    if (!import.meta.env.PROD || !window.isSecureContext) return;
    const onPrompt = (event) => {
      event.preventDefault();
      setPrompt(event);
    };
    const onInstalled = () => {
      setInstalled(true);
      setPrompt(null);
      dialog.current?.close();
    };
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  const available = import.meta.env.PROD && window.isSecureContext && !installed && (prompt || manualKey);
  const install = async () => {
    if (!prompt) {
      dialog.current?.showModal();
      return;
    }
    setPrompt(null);
    try {
      const { outcome } = await prompt.prompt();
      if (outcome === "accepted") setInstalled(true);
    } catch {
      // The browser can invalidate a deferred prompt before it is used.
      if (manualKey) dialog.current?.showModal();
    }
  };

  return (
    <InstallAppContext.Provider value={available ? { install, label: t("install_hisar") } : null}>
      {children}
      {manualKey && (
        <dialog ref={dialog} className="install-dialog" aria-labelledby="install-title" aria-describedby="install-instructions">
          <img src="/icon-192.png" width="52" height="52" alt="" />
          <h2 id="install-title">{t("install_hisar")}</h2>
          <p id="install-instructions">{t(manualKey)}</p>
          <form method="dialog">
            <button type="submit">{t("install_done")}</button>
          </form>
        </dialog>
      )}
    </InstallAppContext.Provider>
  );
}

export function InstallAppButton({ className }) {
  const action = useContext(InstallAppContext);
  if (!action) return null;
  return <button type="button" className={className} onClick={action.install}>{action.label}</button>;
}
