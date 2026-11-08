import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./hisar.jsx";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);

if (import.meta.env.PROD && "serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js", { updateViaCache: "none" }).catch((error) => {
    console.warn("Hisar could not enable offline navigation.", error);
  });
}
