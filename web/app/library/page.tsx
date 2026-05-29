'use client';

import { useEffect, useRef, useState } from 'react';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';
import { useI18n } from '@/lib/i18n';
import { BookUser, Mountain, Smile, Activity, Shirt, Upload, X, Trash2, Loader2 } from 'lucide-react';

type Tab = 'characters' | 'scenes' | 'expressions' | 'actions' | 'wardrobe';

const TAB_ICONS = {
  characters: BookUser,
  scenes: Mountain,
  expressions: Smile,
  actions: Activity,
  wardrobe: Shirt,
};

type LoadState = 'loading' | 'ready' | 'error';

const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error('读取文件失败'));
    reader.readAsDataURL(file);
  });
}

export default function LibraryPage() {
  const { t, locale } = useI18n();
  const { ensureGuest } = useAuth();
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

  const [uploadOpen, setUploadOpen] = useState<null | 'characters' | 'scenes'>(null);

  const reloadChars = () =>
    api.listLibraryCharacters()
      .then((d) => { setChars(d); setCharsState('ready'); })
      .catch((e) => { setCharsState('error'); setErrMsg(e?.message ?? String(e)); });

  const reloadScenes = () =>
    api.listLibraryScenes()
      .then((d) => { setScenes(d); setScenesState('ready'); })
      .catch((e) => { setScenesState('error'); setErrMsg(e?.message ?? String(e)); });

  useEffect(() => {
    reloadChars();
    reloadScenes();
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

  const onDeleteChar = async (charId: string) => {
    if (!confirm(locale === 'en' ? 'Delete this template?' : '确定删除该角色模板？')) return;
    try {
      await api.deleteLibraryCharacter(charId);
      await reloadChars();
    } catch (e: any) {
      alert((locale === 'en' ? 'Delete failed: ' : '删除失败：') + (e?.message ?? String(e)));
    }
  };

  const onDeleteScene = async (sceneId: string) => {
    if (!confirm(locale === 'en' ? 'Delete this template?' : '确定删除该场景模板？')) return;
    try {
      await api.deleteLibraryScene(sceneId);
      await reloadScenes();
    } catch (e: any) {
      alert((locale === 'en' ? 'Delete failed: ' : '删除失败：') + (e?.message ?? String(e)));
    }
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
          ? 'Character / scene / expression / action / wardrobe catalogs for the storyboard layer. Upload your own templates.'
          : '角色 / 场景 / 表情 / 动作 / 服饰库 — 分镜层可直接调用，并支持上传你自己的角色 / 场景模板。'}
      </p>

      <div className="flex flex-wrap items-center gap-2 mb-6">
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

        {(tab === 'characters' || tab === 'scenes') && (
          <button
            onClick={() => setUploadOpen(tab)}
            className="ml-auto inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-cinnabar-600 text-white text-sm font-semibold hover:bg-cinnabar-700 transition"
          >
            <Upload className="w-4 h-4" />
            {tab === 'characters'
              ? (locale === 'en' ? 'Upload character' : '上传角色模板')
              : (locale === 'en' ? 'Upload scene' : '上传场景模板')}
          </button>
        )}
      </div>

      {tab === 'characters' && (
        <div className="grid md:grid-cols-3 gap-4">
          {chars.map((c) => (
            <div key={c.char_id} className="card p-5 relative">
              {c.source === 'user' && (
                <>
                  <span className="absolute top-3 right-3 badge bg-emerald-100 text-emerald-700 text-xs">
                    {locale === 'en' ? 'Mine' : '我的'}
                  </span>
                  <button
                    onClick={() => onDeleteChar(c.char_id)}
                    title={locale === 'en' ? 'Delete' : '删除'}
                    className="absolute bottom-3 right-3 p-1.5 rounded-md text-ink-400 hover:text-red-600 hover:bg-red-50 transition"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </>
              )}
              <h3 className="font-serif text-xl text-ink-900 mb-1">{c.name_zh || c.char_id}</h3>
              <div className="text-xs text-ink-500 font-mono mb-3">{c.role || c.char_id}</div>
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
              {c.voice && (
                <div className="text-xs text-ink-500 mt-2">🎙 {c.voice}</div>
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
            <div key={s.id} className="card p-5 relative">
              {s.source === 'user' && (
                <>
                  <span className="absolute top-3 right-3 badge bg-emerald-100 text-emerald-700 text-xs">
                    {locale === 'en' ? 'Mine' : '我的'}
                  </span>
                  <button
                    onClick={() => onDeleteScene(s.id)}
                    title={locale === 'en' ? 'Delete' : '删除'}
                    className="absolute bottom-3 right-3 p-1.5 rounded-md text-ink-400 hover:text-red-600 hover:bg-red-50 transition"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </>
              )}
              <div className="badge bg-cinnabar-100 text-cinnabar-800 mb-2">{s.category}</div>
              <h3 className="font-serif text-lg text-ink-900 mb-1">{s.name_zh || s.id}</h3>
              {s.preview_cover_url && (
                <img
                  src={s.preview_cover_url}
                  alt={s.name_zh}
                  className="w-full aspect-video object-cover rounded my-2"
                />
              )}
              {s.description && <p className="text-xs text-ink-600 mb-2">{s.description}</p>}
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

      {uploadOpen === 'characters' && (
        <UploadCharacterModal
          locale={locale}
          ensureGuest={ensureGuest}
          onClose={() => setUploadOpen(null)}
          onDone={async () => { setUploadOpen(null); await reloadChars(); setTab('characters'); }}
        />
      )}
      {uploadOpen === 'scenes' && (
        <UploadSceneModal
          locale={locale}
          ensureGuest={ensureGuest}
          onClose={() => setUploadOpen(null)}
          onDone={async () => { setUploadOpen(null); await reloadScenes(); setTab('scenes'); }}
        />
      )}
    </div>
  );
}

interface ModalProps {
  locale: string;
  ensureGuest: () => Promise<void>;
  onClose: () => void;
  onDone: () => void | Promise<void>;
}

function ImagePicker({
  locale, preview, onPick,
}: { locale: string; preview: string | null; onPick: (f: File | null) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <div>
      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif"
        className="hidden"
        onChange={(e) => onPick(e.target.files?.[0] ?? null)}
      />
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        className="w-full border-2 border-dashed border-ink-200 rounded-lg p-4 text-sm text-ink-500 hover:border-cinnabar-400 transition flex flex-col items-center gap-2"
      >
        {preview ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={preview} alt="preview" className="max-h-40 rounded object-contain" />
        ) : (
          <>
            <Upload className="w-6 h-6" />
            {locale === 'en' ? 'Click to pick an image (≤5MB)' : '点击选择参考图（≤5MB，PNG/JPG/WebP）'}
          </>
        )}
      </button>
    </div>
  );
}

function ModalShell({
  title, onClose, children,
}: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-ink-100 sticky top-0 bg-white rounded-t-2xl">
          <h2 className="font-serif text-xl text-ink-900">{title}</h2>
          <button onClick={onClose} className="text-ink-400 hover:text-ink-700">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="px-6 py-5 space-y-4">{children}</div>
      </div>
    </div>
  );
}

const inputCls =
  'w-full border border-ink-200 rounded-lg px-3 py-2 text-sm focus:border-cinnabar-500 focus:outline-none';
const labelCls = 'block text-sm font-semibold text-ink-700 mb-1';

function UploadCharacterModal({ locale, ensureGuest, onClose, onDone }: ModalProps) {
  const [name, setName] = useState('');
  const [role, setRole] = useState('');
  const [age, setAge] = useState('');
  const [voice, setVoice] = useState('');
  const [marks, setMarks] = useState('');
  const [imageData, setImageData] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const pick = async (f: File | null) => {
    setErr(null);
    if (!f) { setImageData(null); return; }
    if (f.size > MAX_IMAGE_BYTES) { setErr(locale === 'en' ? 'Image too large (≤5MB)' : '图片过大（上限 5MB）'); return; }
    try { setImageData(await fileToDataUrl(f)); } catch (e: any) { setErr(e?.message ?? String(e)); }
  };

  const submit = async () => {
    setErr(null);
    if (!name.trim()) { setErr(locale === 'en' ? 'Name is required' : '请填写角色名称'); return; }
    setBusy(true);
    try {
      await ensureGuest();
      await api.uploadLibraryCharacter({
        name_zh: name.trim(),
        role: role.trim() || undefined,
        age: age ? Number(age) : null,
        voice: voice.trim() || undefined,
        signature_marks: marks.split('\n').map((s) => s.trim()).filter(Boolean),
        image_base64: imageData,
      });
      await onDone();
    } catch (e: any) {
      setErr(e?.message ?? String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <ModalShell title={locale === 'en' ? 'Upload character template' : '上传角色模板'} onClose={onClose}>
      <div>
        <label className={labelCls}>{locale === 'en' ? 'Name *' : '角色名称 *'}</label>
        <input className={inputCls} value={name} onChange={(e) => setName(e.target.value)}
          placeholder={locale === 'en' ? 'e.g. Nie Xiaoqian' : '例如：聂小倩'} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelCls}>{locale === 'en' ? 'Role' : '角色定位'}</label>
          <input className={inputCls} value={role} onChange={(e) => setRole(e.target.value)}
            placeholder={locale === 'en' ? 'Heroine / villain…' : '女主角 / 反派…'} />
        </div>
        <div>
          <label className={labelCls}>{locale === 'en' ? 'Age' : '年龄'}</label>
          <input className={inputCls} type="number" value={age} onChange={(e) => setAge(e.target.value)} />
        </div>
      </div>
      <div>
        <label className={labelCls}>{locale === 'en' ? 'Signature marks (one per line)' : '锁定符号（每行一条）'}</label>
        <textarea className={inputCls} rows={3} value={marks} onChange={(e) => setMarks(e.target.value)}
          placeholder={locale === 'en' ? 'Red dot between brows…' : '眉间一点朱砂痣…'} />
      </div>
      <div>
        <label className={labelCls}>{locale === 'en' ? 'Voice' : '声线'}</label>
        <input className={inputCls} value={voice} onChange={(e) => setVoice(e.target.value)}
          placeholder={locale === 'en' ? 'Cool ethereal female voice…' : '清冷空灵女音…'} />
      </div>
      <div>
        <label className={labelCls}>{locale === 'en' ? 'Reference image' : '参考图（首帧/立绘）'}</label>
        <ImagePicker locale={locale} preview={imageData} onPick={pick} />
      </div>
      {err && <div className="text-xs text-red-600">{err}</div>}
      <div className="flex justify-end gap-2 pt-2">
        <button onClick={onClose} className="px-4 py-2 rounded-lg border border-ink-200 text-sm text-ink-700">
          {locale === 'en' ? 'Cancel' : '取消'}
        </button>
        <button onClick={submit} disabled={busy}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-cinnabar-600 text-white text-sm font-semibold hover:bg-cinnabar-700 disabled:opacity-60">
          {busy && <Loader2 className="w-4 h-4 animate-spin" />}
          {locale === 'en' ? 'Upload' : '上传'}
        </button>
      </div>
    </ModalShell>
  );
}

function UploadSceneModal({ locale, ensureGuest, onClose, onDone }: ModalProps) {
  const [name, setName] = useState('');
  const [category, setCategory] = useState('');
  const [description, setDescription] = useState('');
  const [keywords, setKeywords] = useState('');
  const [imageData, setImageData] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const pick = async (f: File | null) => {
    setErr(null);
    if (!f) { setImageData(null); return; }
    if (f.size > MAX_IMAGE_BYTES) { setErr(locale === 'en' ? 'Image too large (≤5MB)' : '图片过大（上限 5MB）'); return; }
    try { setImageData(await fileToDataUrl(f)); } catch (e: any) { setErr(e?.message ?? String(e)); }
  };

  const submit = async () => {
    setErr(null);
    if (!name.trim()) { setErr(locale === 'en' ? 'Name is required' : '请填写场景名称'); return; }
    setBusy(true);
    try {
      await ensureGuest();
      await api.uploadLibraryScene({
        name_zh: name.trim(),
        category: category.trim() || undefined,
        description: description.trim() || undefined,
        keywords: keywords.split(/[,\n]/).map((s) => s.trim()).filter(Boolean),
        image_base64: imageData,
      });
      await onDone();
    } catch (e: any) {
      setErr(e?.message ?? String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <ModalShell title={locale === 'en' ? 'Upload scene template' : '上传场景模板'} onClose={onClose}>
      <div>
        <label className={labelCls}>{locale === 'en' ? 'Name *' : '场景名称 *'}</label>
        <input className={inputCls} value={name} onChange={(e) => setName(e.target.value)}
          placeholder={locale === 'en' ? 'e.g. Lanruo Temple' : '例如：兰若寺'} />
      </div>
      <div>
        <label className={labelCls}>{locale === 'en' ? 'Category' : '分类'}</label>
        <input className={inputCls} value={category} onChange={(e) => setCategory(e.target.value)}
          placeholder={locale === 'en' ? 'Ancient temple / wild…' : '古风寺庙 / 野外…'} />
      </div>
      <div>
        <label className={labelCls}>{locale === 'en' ? 'Description' : '场景描述'}</label>
        <textarea className={inputCls} rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
      </div>
      <div>
        <label className={labelCls}>{locale === 'en' ? 'Keywords (comma / line separated)' : '关键词（逗号或换行分隔）'}</label>
        <input className={inputCls} value={keywords} onChange={(e) => setKeywords(e.target.value)}
          placeholder={locale === 'en' ? 'night, moonlight, ruins' : '夜晚, 月光, 破败'} />
      </div>
      <div>
        <label className={labelCls}>{locale === 'en' ? 'Reference image' : '参考图'}</label>
        <ImagePicker locale={locale} preview={imageData} onPick={pick} />
      </div>
      {err && <div className="text-xs text-red-600">{err}</div>}
      <div className="flex justify-end gap-2 pt-2">
        <button onClick={onClose} className="px-4 py-2 rounded-lg border border-ink-200 text-sm text-ink-700">
          {locale === 'en' ? 'Cancel' : '取消'}
        </button>
        <button onClick={submit} disabled={busy}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-cinnabar-600 text-white text-sm font-semibold hover:bg-cinnabar-700 disabled:opacity-60">
          {busy && <Loader2 className="w-4 h-4 animate-spin" />}
          {locale === 'en' ? 'Upload' : '上传'}
        </button>
      </div>
    </ModalShell>
  );
}
