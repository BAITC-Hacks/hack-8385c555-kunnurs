import React, { createContext, useContext, useEffect, useState } from 'react';
import { translate } from './translations';

const LanguageContext = createContext(null);
const STORAGE_KEY = 'akim-language';
const languages = [{ code: 'ru', label: 'RU', name: 'Русский' }, { code: 'kk', label: 'ҚАЗ', name: 'Қазақша' }, { code: 'en', label: 'EN', name: 'English' }];
const groupLabels = { ru: 'Язык интерфейса', kk: 'Интерфейс тілі', en: 'Interface language' };

export function useTranslation() {
  const { locale } = useContext(LanguageContext);
  return (text) => translate(text, locale);
}

export function LanguageProvider({ children }) {
  const [locale, setLocale] = useState(() => {
    try { const saved = localStorage.getItem(STORAGE_KEY); return languages.some((l) => l.code === saved) ? saved : 'ru'; }
    catch { return 'ru'; }
  });
  useEffect(() => {
    document.documentElement.lang = locale;
    document.title = translate('Аким на 5 часов', locale);
    try { localStorage.setItem(STORAGE_KEY, locale); } catch { /* Works in memory when storage is unavailable. */ }
  }, [locale]);
  return <LanguageContext.Provider value={{ locale, setLocale }}>{children}</LanguageContext.Provider>;
}

export function LanguageSwitcher() {
  const { locale, setLocale } = useContext(LanguageContext);
  return <div className="language-switcher" role="group" aria-label={groupLabels[locale]}>
    <svg className="language-globe" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><circle cx="12" cy="12" r="9" /><ellipse cx="12" cy="12" rx="4" ry="9" /><path d="M3 12h18M5 6h14M5 18h14" /></svg>
    {languages.map(({ code, label, name }) => <button key={code} type="button" lang={code} data-language={code} aria-label={name} title={name} aria-pressed={locale === code} onClick={() => setLocale(code)}>{label}</button>)}
  </div>;
}

// Translate React-owned text at render time, preserving elements, keys, handlers and state.
// Components opt in at their boundary; no DOM rewriting or dataset mutation is used.
function localizeNode(node, locale) {
  if (typeof node === 'string') return translate(node, locale);
  if (Array.isArray(node)) return node.map((child) => localizeNode(child, locale));
  if (!React.isValidElement(node) || node.props['data-original-text']) return node;
  const props = {};
  for (const key of ['aria-label', 'title', 'placeholder', 'label']) if (typeof node.props[key] === 'string') props[key] = translate(node.props[key], locale);
  if (node.props.children !== undefined) props.children = localizeNode(node.props.children, locale);
  return React.cloneElement(node, props);
}

export function Localized({ children }) {
  const { locale } = useContext(LanguageContext);
  return localizeNode(children, locale);
}

export function OriginalLanguageNotice() {
  const { locale } = useContext(LanguageContext);
  return locale === 'ru' ? null : <p className="original-language-note">{translate('Серверный разбор и описание компромиссов предоставлены на русском языке.', locale)}</p>;
}
