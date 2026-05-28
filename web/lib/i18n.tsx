'use client';

import React, { createContext, useContext, useEffect, useState, useCallback, ReactNode } from 'react';
import zhCN from './i18n/zh-CN.json';
import en from './i18n/en.json';

type Locale = 'zh-CN' | 'en';

const BUNDLES: Record<Locale, any> = {
  'zh-CN': zhCN,
  en: en,
};

const LOCALE_KEY = 'xyq_locale';

interface I18nContextValue {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: string, fallback?: string) => string;
}

const I18nContext = createContext<I18nContextValue>({
  locale: 'zh-CN',
  setLocale: () => {},
  t: (_k, f) => f ?? '',
});

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>('zh-CN');

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const saved = (localStorage.getItem(LOCALE_KEY) as Locale | null) ?? null;
    if (saved === 'zh-CN' || saved === 'en') {
      setLocaleState(saved);
      return;
    }
    setLocaleState('zh-CN');
  }, []);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    if (typeof window !== 'undefined') {
      localStorage.setItem(LOCALE_KEY, l);
      document.documentElement.lang = l;
    }
  }, []);

  const t = useCallback(
    (key: string, fallback?: string) => {
      const path = key.split('.');
      let cur: any = BUNDLES[locale];
      for (const p of path) {
        if (cur && typeof cur === 'object' && p in cur) {
          cur = cur[p];
        } else {
          cur = null;
          break;
        }
      }
      if (typeof cur === 'string') return cur;
      // Fallback to zh-CN bundle if missing
      let zh: any = BUNDLES['zh-CN'];
      for (const p of path) {
        if (zh && typeof zh === 'object' && p in zh) {
          zh = zh[p];
        } else {
          zh = null;
          break;
        }
      }
      if (typeof zh === 'string') return zh;
      return fallback ?? key;
    },
    [locale]
  );

  return (
    <I18nContext.Provider value={{ locale, setLocale, t }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  return useContext(I18nContext);
}

export function LocaleSwitcher({ className = '' }: { className?: string }) {
  const { locale, setLocale } = useI18n();
  return (
    <div className={`inline-flex items-center gap-1 text-xs ${className}`}>
      <button
        onClick={() => setLocale('zh-CN')}
        className={`px-2 py-1 rounded ${
          locale === 'zh-CN' ? 'bg-cinnabar-100 text-cinnabar-800 font-semibold' : 'text-ink-500'
        }`}
        aria-label="Switch to Chinese"
      >
        中
      </button>
      <span className="text-ink-300">/</span>
      <button
        onClick={() => setLocale('en')}
        className={`px-2 py-1 rounded ${
          locale === 'en' ? 'bg-cinnabar-100 text-cinnabar-800 font-semibold' : 'text-ink-500'
        }`}
        aria-label="Switch to English"
      >
        EN
      </button>
    </div>
  );
}
