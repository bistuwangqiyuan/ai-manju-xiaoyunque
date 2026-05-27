'use client';

import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { useI18n, LocaleSwitcher } from '@/lib/i18n';
import { formatYuan } from '@/lib/utils';
import { Sparkles, Crown, Building2, Shield, Menu, X } from 'lucide-react';
import { useState } from 'react';
import type { Tier } from '@/lib/api';

const TIER_META: Record<Tier, { label: string; icon: typeof Sparkles; cls: string }> = {
  free:   { label: 'Free',   icon: Sparkles,   cls: 'bg-ink-100 text-ink-700' },
  pro:    { label: 'Pro',    icon: Crown,      cls: 'bg-cinnabar-100 text-cinnabar-800' },
  studio: { label: 'Studio', icon: Building2,  cls: 'bg-emerald-100 text-emerald-800' },
  admin:  { label: 'Admin',  icon: Shield,     cls: 'bg-purple-100 text-purple-800' },
};

type NavLink = { href: string; key: string; requiresAuth?: boolean };

const PRIMARY_LINKS: NavLink[] = [
  { href: '/dashboard', key: 'nav.studio', requiresAuth: true },
  { href: '/templates', key: 'nav.templates' },
  { href: '/library', key: 'nav.library', requiresAuth: true },
  { href: '/batch', key: 'nav.batch', requiresAuth: true },
];

const SECONDARY_LINKS: NavLink[] = [
  { href: '/guide', key: 'nav.guide' },
  { href: '/quality', key: 'nav.quality' },
  { href: '/pricing', key: 'nav.pricing' },
];

export function Nav() {
  const { user, signOut, loading } = useAuth();
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const tierMeta = user ? TIER_META[user.tier] || TIER_META.free : null;

  return (
    <header className="sticky top-0 z-30 border-b border-ink-200/60 bg-ink-50/80 backdrop-blur">
      <div className="mx-auto max-w-7xl px-6 h-16 flex items-center justify-between gap-3">
        <Link href="/" className="flex items-center gap-2 font-serif text-xl text-ink-900 shrink-0">
          <span className="seal text-base w-9 h-9">雀</span>
          <span className="font-semibold tracking-wide hidden sm:inline">小云雀 · 漫剧产线</span>
        </Link>

        {/* Desktop nav */}
        <nav className="hidden lg:flex items-center gap-1 flex-1 justify-center">
          {PRIMARY_LINKS.map((l) => {
            if (l.requiresAuth && !user) return null;
            return (
              <Link key={l.href} href={l.href} className="btn-ghost text-sm">
                {t(l.key)}
              </Link>
            );
          })}
          {SECONDARY_LINKS.map((l) => (
            <Link key={l.href} href={l.href} className="btn-ghost text-sm text-ink-600">
              {t(l.key)}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <LocaleSwitcher className="hidden sm:inline-flex" />
          {user && tierMeta ? (
            <>
              <span className={`hidden md:inline-flex badge ${tierMeta.cls}`}>
                <tierMeta.icon className="w-3 h-3 mr-1" />
                {tierMeta.label}
              </span>
              <span className="hidden xl:inline-flex badge bg-ink-100 text-ink-700">
                {formatYuan(user.credits_cents)}
              </span>
              <button onClick={signOut} className="btn-ghost text-sm">{t('nav.logout')}</button>
            </>
          ) : loading ? null : (
            <>
              <Link href="/login" className="btn-ghost text-sm">{t('nav.login')}</Link>
              <Link href="/signup" className="btn-primary text-sm">{t('nav.signup')}</Link>
            </>
          )}

          {/* Mobile burger */}
          <button
            className="lg:hidden btn-ghost p-2"
            onClick={() => setOpen((o) => !o)}
            aria-label="Menu"
          >
            {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {open && (
        <nav className="lg:hidden border-t border-ink-200/60 bg-ink-50/95 backdrop-blur">
          <div className="px-6 py-3 grid gap-1">
            {[...PRIMARY_LINKS, ...SECONDARY_LINKS].map((l) => {
              if (l.requiresAuth && !user) return null;
              return (
                <Link
                  key={l.href}
                  href={l.href}
                  className="px-3 py-2 rounded hover:bg-cinnabar-50 text-sm text-ink-800"
                  onClick={() => setOpen(false)}
                >
                  {t(l.key)}
                </Link>
              );
            })}
            <LocaleSwitcher className="mt-2" />
          </div>
        </nav>
      )}
    </header>
  );
}
