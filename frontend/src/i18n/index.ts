import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import en from "./locales/en.json";
import vi from "./locales/vi.json";

// NauAgency deployment intentionally exposes only Vietnamese and English.
// Vietnamese is first and is the default for a browser without a saved choice.
export const SUPPORTED_LANGUAGES = [
  { code: "vi", label: "Tiếng Việt", dir: "ltr" as const },
  { code: "en", label: "English", dir: "ltr" as const },
] as const;

export type SupportedLanguageCode = (typeof SUPPORTED_LANGUAGES)[number]["code"];

export function isRtl(_code: string): boolean {
  return false;
}

export function applyDocumentDirection(code: string): void {
  if (typeof document === "undefined") return;
  document.documentElement.setAttribute("dir", "ltr");
  document.documentElement.setAttribute("lang", code === "en" ? "en" : "vi");
}

i18n.on("languageChanged", applyDocumentDirection);

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      vi: { translation: vi },
      en: { translation: en },
    },
    initAsync: false,
    fallbackLng: "vi",
    supportedLngs: SUPPORTED_LANGUAGES.map((language) => language.code),
    interpolation: { escapeValue: false },
    detection: {
      order: ["localStorage"],
      caches: ["localStorage"],
      lookupLocalStorage: "i18nextLng",
    },
  });

applyDocumentDirection(i18n.language || "vi");

export default i18n;
