/* ============================================================
   i18n — inicialización de react-i18next (en/es).
   Inglés por defecto (igual que el diseño original); el idioma
   elegido se persiste en localStorage y se sincroniza con <html lang>.
   ============================================================ */
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./en.json";
import es from "./es.json";

const STORAGE_KEY = "term.lang";

function savedLang() {
  try {
    const s = localStorage.getItem(STORAGE_KEY);
    return s === "en" || s === "es" ? s : null;
  } catch {
    return null;
  }
}

i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, es: { translation: es } },
  lng: savedLang() || "en",
  fallbackLng: "en",
  supportedLngs: ["en", "es"],
  interpolation: { escapeValue: false }, // React ya escapa; permite ·, −, $, % en los textos
  react: { useSuspense: false },
});

// persistir el idioma elegido + reflejarlo en el documento
i18n.on("languageChanged", (lng) => {
  try { localStorage.setItem(STORAGE_KEY, lng); } catch { /* almacenamiento no disponible */ }
  if (typeof document !== "undefined") document.documentElement.lang = lng;
});
if (typeof document !== "undefined") document.documentElement.lang = i18n.language;

export default i18n;
