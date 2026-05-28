'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { useI18n } from '@/lib/i18n';
import { BookUser, Mountain, Smile, Activity, Shirt } from 'lucide-react';

type Tab = 'characters' | 'scenes' | 'expressions' | 'actions' | 'wardrobe';

const TAB_ICONS = {
  characters: BookUser,
  scenes: Mountain,
  expressions: Smile,
  actions: Activity,
  wardrobe: Shirt,
};

type LoadState = 'loading' | 'ready' | 'error';

export default function LibraryPage() {
  const { t, locale } = useI18n();
  const [tab, setTab] = useState<Tab>('characters');
  const [chars, setChars] = useState<any[]>([]);
  const [scenes, setScenes] = useState<any[]>([]);
  const [expressions, setExpressions] = useState<any[]>([]);
  const [actions, setActions] = useState<any[]>([]);
  const [wardrobe, setWardrobe] = useState<any[]>([]);
  const [charsState, setCharsState] = useState<LoadState>('loading');
  const [scenesState, setScenesState] = useState<LoadState>('loading');
  const [exprState, setExprState] = useState<LoadState>('loading');
  const [actState, setActState] = useState<LoadState>('loading');
  const [wardState, setWardState] = useState<LoadState>('loading');
  const [errMsg, setErrMsg] = useState<string | null>(null);

  useEffect(() => {
    api.listLibraryCharacters()
      .then((d) => { setChars(d); setCharsState('ready'); })
      .catch((e) => { setCharsState('error'); setErrMsg(e?.message ?? String(e)); });
    api.listLibraryScenes()
      .then((d) => { setScenes(d); setScenesState('ready'); })
      .catch((e) => { setScenesState('error'); setErrMsg(e?.message ?? String(e)); });
    api.listExpressionKeys()
      .then((d) => { setExpressions(d); setExprState('ready'); })
      .catch((e) => { setExprState('error'); setErrMsg(e?.message ?? String(e)); });
    api.listActionKeys()
      .then((d) => { setActions(d); setActState('ready'); })
      .catch((e) => { setActState('error'); setErrMsg(e?.message ?? String(e)); });
    api.listWardrobeKeys()
      .then((d) => { setWardrobe(d); setWardState('ready'); })
      .catch((e) => { setWardState('error'); setErrMsg(e?.message ?? String(e)); });
  }, []);

  const emptyHint = (s: LoadState, hasData: boolean) => {
    if (hasData) return null;
    if (s === 'loading') return locale === 'en' ? 'Loading…' : '加载中…';
    if (s === 'error') return locale === 'en' ? 'Failed to load' : '加载失败，请刷新重试';
    return locale === 'en' ? 'No data yet' : '暂无数据';
  };

  const tabs: { id: Tab; label: string; count: number }[] = [
    { id: 'characters', label: t('library.characters'), count: chars.length },
    { id: 'scenes', label: t('library.scenes'), count: scenes.length },
    { id: 'expressions', label: t('library.expressions'), count: expressions.length },
    { id: 'actions', label: t('library.actions'), count: actions.length },
    { id: 'wardrobe', label: t('library.wardrobe'), count: wardrobe.length },
  ];

  return (
    <div className="mx-auto max-w-6xl px-6 py-12">
      <h1 className="font-serif text-4xl text-ink-900 mb-2">{t('library.title')}</h1>
      <p className="text-ink-600 mb-6">
        {locale === 'en'
          ? 'Character / scene / expression / action / wardrobe catalogs for the storyboard layer.'
          : '角色 / 场景 / 表情 / 动作 / 服饰库 — 分镜层可直接调用。'}
      </p>

      <div className="flex flex-wrap gap-2 mb-6">
        {tabs.map((tt) => {
          const Icon = TAB_ICONS[tt.id];
          const active = tab === tt.id;
          return (
            <button
              key={tt.id}
              onClick={() => setTab(tt.id)}
              className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg border text-sm transition ${
                active
                  ? 'border-cinnabar-600 bg-cinnabar-50 text-cinnabar-800 font-semibold'
                  : 'border-ink-200 hover:border-ink-400 text-ink-700'
              }`}
            >
              <Icon className="w-4 h-4" />
              {tt.label}
              <span className="text-xs text-ink-500">({tt.count})</span>
            </button>
          );
        })}
      </div>

      {tab === 'characters' && (
        <div className="grid md:grid-cols-3 gap-4">
          {chars.map((c) => (
            <div key={c.char_id} className="card p-5">
              <h3 className="font-serif text-xl text-ink-900 mb-1">{c.name_zh || c.char_id}</h3>
              <div className="text-xs text-ink-500 font-mono mb-3">{c.char_id}</div>
              {c.canonical_image_url && (
                <img
                  src={c.canonical_image_url}
                  alt={c.name_zh}
                  className="w-full aspect-[3/4] object-cover rounded mb-3"
                />
              )}
              {Array.isArray(c.signature_marks) && c.signature_marks.length > 0 && (
                <div className="text-xs text-ink-600 mb-2">
                  <div className="font-semibold mb-1">{locale === 'en' ? 'Signature marks' : '锁定符号'}</div>
                  <ul className="space-y-0.5">
                    {c.signature_marks.slice(0, 3).map((s: string, i: number) => (
                      <li key={i}>· {s}</li>
                    ))}
                  </ul>
                </div>
              )}
              {c.stub && (
                <div className="badge bg-amber-100 text-amber-800 text-xs">stub manifest</div>
              )}
            </div>
          ))}
          {chars.length === 0 && (
            <div className="col-span-full text-ink-500 py-8 text-center">{emptyHint(charsState, false)}</div>
          )}
        </div>
      )}

      {tab === 'scenes' && (
        <div className="grid md:grid-cols-3 gap-4">
          {scenes.map((s) => (
            <div key={s.id} className="card p-5">
              <div className="badge bg-cinnabar-100 text-cinnabar-800 mb-2">{s.category}</div>
              <h3 className="font-serif text-lg text-ink-900 mb-1">{s.name_zh || s.id}</h3>
              <div className="text-xs text-ink-500 font-mono mb-2">{s.id}</div>
              <div className="text-xs text-ink-600 flex flex-wrap gap-1">
                {(s.keywords || []).map((k: string) => (
                  <span key={k} className="badge bg-ink-100 text-ink-700">#{k}</span>
                ))}
              </div>
            </div>
          ))}
          {scenes.length === 0 && (
            <div className="col-span-full text-ink-500 py-8 text-center">{emptyHint(scenesState, false)}</div>
          )}
        </div>
      )}

      {tab === 'expressions' && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {expressions.map((e) => (
            <div key={e.key} className="card p-4">
              <div className="font-serif text-2xl text-cinnabar-700 mb-1">{e.name_zh}</div>
              <div className="text-xs text-ink-500 font-mono mb-2">{e.key}</div>
              <p className="text-xs text-ink-700">{e.description}</p>
            </div>
          ))}
          {expressions.length === 0 && (
            <div className="col-span-full text-ink-500 py-8 text-center">{emptyHint(exprState, false)}</div>
          )}
        </div>
      )}

      {tab === 'actions' && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {actions.map((a) => (
            <div key={a.key} className="card p-4">
              <div className="font-serif text-xl text-cinnabar-700 mb-1">{a.name_zh}</div>
              <div className="text-xs text-ink-500 font-mono mb-2">{a.key}</div>
              <p className="text-xs text-ink-700">{a.description}</p>
            </div>
          ))}
          {actions.length === 0 && (
            <div className="col-span-full text-ink-500 py-8 text-center">{emptyHint(actState, false)}</div>
          )}
        </div>
      )}

      {tab === 'wardrobe' && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {wardrobe.map((w) => (
            <div key={w.key} className="card p-4">
              <div className="font-serif text-lg text-ink-900 mb-1">{w.name_zh}</div>
              <div className="text-xs text-ink-500 font-mono mb-2">{w.key}</div>
              <p className="text-xs text-ink-700">{w.description}</p>
            </div>
          ))}
          {wardrobe.length === 0 && (
            <div className="col-span-full text-ink-500 py-8 text-center">{emptyHint(wardState, false)}</div>
          )}
        </div>
      )}

      {errMsg && (
        <div className="mt-6 p-3 rounded-lg bg-red-50 text-red-700 text-xs">
          {locale === 'en' ? 'Some lists failed: ' : '部分接口加载失败：'}{errMsg}
        </div>
      )}
    </div>
  );
}
