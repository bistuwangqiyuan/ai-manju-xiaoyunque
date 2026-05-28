import Link from 'next/link';
import {
  ArrowLeft,
  BookOpen,
  Sparkles,
  UserPlus,
  Wallet,
  Wand2,
  Film,
  Award,
  Download,
  Library,
  Layers,
  RefreshCw,
  HelpCircle,
  Crown,
  FileText,
  Upload,
  Type,
} from 'lucide-react';

export const metadata = {
  title: '使用说明 · 小云雀 AI 漫剧',
  description:
    '普通用户操作手册：注册、创作、质检、导出与常见问题。把小说一键变成 9:16 古风漫剧视频。',
};

const TOC = [
  { id: 'intro', label: '1. 产品简介' },
  { id: 'quickstart', label: '2. 三步快速上手' },
  { id: 'account', label: '3. 注册与登录' },
  { id: 'quota', label: '4. 账户等级与配额' },
  { id: 'create', label: '5. 创建漫剧' },
  { id: 'progress', label: '6. 生成进度与六步流程' },
  { id: 'job', label: '7. 作品详情页' },
  { id: 'shots', label: '8. 镜头质检与 7 维评分' },
  { id: 'versions', label: '9. 版本中心' },
  { id: 'export', label: '10. 多平台导出' },
  { id: 'showcase', label: '11. 作品广场' },
  { id: 'templates', label: '12. 爆款模板库' },
  { id: 'library', label: '13. 资产库' },
  { id: 'batch', label: '14. 批量转绘' },
  { id: 'faq', label: '15. 常见问题' },
];

const PIPELINE_STEPS = [
  { n: 1, title: '剧本分析', desc: '解析小说片段，提取人物、场景与情节结构，并通过合规审核。' },
  { n: 2, title: '人物/道具/资产包', desc: '生成角色三视图、场景、表情与服饰等视觉资产。' },
  { n: 3, title: '分镜提示词', desc: '按镜头拆分画面，编写每镜的 AI 绘制指令。' },
  { n: 4, title: '抽卡生视频', desc: '逐镜渲染画面并合成动态视频片段（最耗时的一步）。' },
  { n: 5, title: '初期粗剪', desc: '拼接镜头、铺入配音与背景音乐。' },
  { n: 6, title: '精剪审核', desc: '7 维质检、自动修复、字幕与成片输出。' },
];

function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-24">
      <h2 className="font-serif text-2xl text-ink-900 mb-4 pb-2 border-b border-ink-200/80">
        {title}
      </h2>
      <div className="space-y-4 text-ink-700 leading-relaxed">{children}</div>
    </section>
  );
}

function Tip({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-emerald-200/80 bg-emerald-50/60 px-4 py-3 text-sm text-emerald-900">
      {children}
    </div>
  );
}

function Warn({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-amber-200/80 bg-amber-50/60 px-4 py-3 text-sm text-amber-900">
      {children}
    </div>
  );
}

export default function GuidePage() {
  return (
    <div className="mx-auto max-w-5xl px-6 py-12">
      <Link href="/" className="btn-ghost text-sm mb-4">
        <ArrowLeft className="w-4 h-4 mr-1" /> 返回首页
      </Link>

      <div className="mb-10">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cinnabar-100 text-cinnabar-800 text-xs font-medium mb-3">
          <BookOpen className="w-3.5 h-3.5" />
          面向普通用户的完整操作手册
        </div>
        <h1 className="font-serif text-4xl text-ink-900 mb-3">小云雀 · 使用说明</h1>
        <p className="text-lg text-ink-700 leading-relaxed max-w-3xl mb-4">
          本手册帮助您从零开始使用「小云雀 AI 漫剧产线」：把一段小说、大纲或主题，
          自动变成可下载的竖屏漫剧视频。无需安装软件，打开浏览器即可操作。
        </p>
        <Tip>
          <strong>在线访问：</strong>{' '}
          <a
            href="https://cursoraicode-5g67ezfl8a1891da-1300352403.tcloudbaseapp.com"
            className="underline font-medium"
            target="_blank"
            rel="noopener noreferrer"
          >
            cursoraicode-5g67ezfl8a1891da-1300352403.tcloudbaseapp.com
          </a>
          {' '}· 注册后从顶部「工作台」开始创作
        </Tip>
      </div>

      {/* 目录 */}
      <nav className="card p-6 mb-12">
        <h2 className="font-semibold text-ink-900 mb-3">目录</h2>
        <ol className="grid sm:grid-cols-2 gap-x-6 gap-y-2 text-sm">
          {TOC.map((item) => (
            <li key={item.id}>
              <a href={`#${item.id}`} className="text-cinnabar-700 hover:underline">
                {item.label}
              </a>
            </li>
          ))}
        </ol>
      </nav>

      <div className="space-y-14">
        <Section id="intro" title="1. 产品简介">
          <p>
            <strong>小云雀</strong>是一款 AI 漫剧生成应用。您只需提供文字素材（小说片段、大纲或一句主题），
            系统会自动完成剧本分析、角色与场景资产、分镜绘制、配音配乐、剪辑合成等全流程，
            最终交付 <strong>9:16 竖屏 MP4 视频</strong>（也支持 16:9、1:1 等专业模式设置）。
          </p>
          <p>支持题材包括：古风、现代、甜宠、悬疑、玄幻等，并可一键套用爆款模板。</p>
          <p>
            每一集成片都会经过工业级质量评分（100 分制），
            <strong>未达 95 分会自动修复重试</strong>，详情见{' '}
            <Link href="/quality" className="text-cinnabar-700 underline">
              评分方法
            </Link>
            。
          </p>
        </Section>

        <Section id="quickstart" title="2. 三步快速上手">
          <div className="grid md:grid-cols-3 gap-4 not-prose">
            {[
              {
                icon: UserPlus,
                title: '注册账号',
                desc: '用邮箱注册，获赠 100 元体验金，Free 用户每天可免费生成 3 集。',
                href: '/signup',
                cta: '去注册',
              },
              {
                icon: FileText,
                title: '粘贴文字',
                desc: '进入工作台 →「做一集新的」，粘贴至少 50 字的小说片段，或输入 4 字以上的主题。',
                href: '/dashboard/new',
                cta: '去创作',
              },
              {
                icon: Download,
                title: '等待并下载',
                desc: '任务完成后在作品页预览视频，点击「下载 MP4」保存到本地。',
                href: '/dashboard',
                cta: '打开工作台',
              },
            ].map((step) => (
              <div key={step.title} className="card p-6 flex flex-col">
                <step.icon className="w-10 h-10 text-cinnabar-600 mb-3" />
                <h3 className="font-serif text-xl text-ink-900 mb-2">{step.title}</h3>
                <p className="text-sm text-ink-600 mb-4 flex-1">{step.desc}</p>
                <Link href={step.href} className="btn-secondary text-sm w-fit">
                  {step.cta}
                </Link>
              </div>
            ))}
          </div>
        </Section>

        <Section id="account" title="3. 注册与登录">
          <h3 className="font-semibold text-ink-900">注册</h3>
          <ol className="list-decimal list-inside space-y-2 text-sm">
            <li>
              打开{' '}
              <Link href="/signup" className="text-cinnabar-700 underline">
                注册页
              </Link>
              ，填写邮箱与密码（至少 8 位）。
            </li>
            <li>注册成功后自动登录，并跳转至「工作台」。</li>
            <li>新用户赠送 <strong>100 元体验金</strong>，可用于 Pro 按量计费。</li>
          </ol>

          <h3 className="font-semibold text-ink-900 mt-6">登录</h3>
          <p className="text-sm">
            已有账号请前往{' '}
            <Link href="/login" className="text-cinnabar-700 underline">
              登录页
            </Link>
            。登录后可从顶部导航进入「工作台」「资产库」「批量转绘」等功能。
          </p>

          <Tip>
            顶部导航栏会显示您的账户等级（Free / Pro）和当前余额。点击「退出」可安全登出。
          </Tip>
        </Section>

        <Section id="quota" title="4. 账户等级与配额">
          <div className="grid sm:grid-cols-2 gap-4 not-prose">
            <div className="card p-5">
              <div className="flex items-center gap-2 mb-2">
                <Sparkles className="w-5 h-5 text-ink-600" />
                <span className="font-serif text-xl text-ink-900">Free 免费版</span>
              </div>
              <ul className="text-sm space-y-1.5 text-ink-700">
                <li>• 每天可免费生成 <strong>3 集</strong></li>
                <li>• 单次任务最多 <strong>1 集</strong></li>
                <li>• 支持全部题材与 1080p MP4 下载</li>
                <li>• 今日配额用完后需次日恢复，或充值升级 Pro</li>
              </ul>
            </div>
            <div className="card p-5 border-cinnabar-200/80">
              <div className="flex items-center gap-2 mb-2">
                <Crown className="w-5 h-5 text-cinnabar-600" />
                <span className="font-serif text-xl text-cinnabar-800">Pro 付费版</span>
              </div>
              <ul className="text-sm space-y-1.5 text-ink-700">
                <li>• 无每日生成数量限制</li>
                <li>• 单次最多 <strong>10 集</strong>套装</li>
                <li>• 按集计费（约 ¥0.72/集起），充值任意金额自动升级</li>
                <li>• 优先队列，支持更多导出规格</li>
              </ul>
            </div>
          </div>
          <p className="text-sm">
            在工作台顶部可查看「今日免费配额」「余额」和「单集费用」。
            充值请前往{' '}
            <Link href="/pricing" className="text-cinnabar-700 underline">
              价格页
            </Link>
            。
          </p>
          <Warn>
            创建任务时会预先扣减配额或余额。若任务在「排队中」或「渲染中」被取消，已扣费用会按比例退回。
          </Warn>
        </Section>

        <Section id="create" title="5. 创建漫剧">
          <p>系统提供三种创作入口，适合不同使用习惯：</p>

          <h3 className="font-semibold text-ink-900">5.1 标准创作（推荐新手）</h3>
          <p className="text-sm">
            路径：<Link href="/dashboard/new" className="text-cinnabar-700 underline">工作台 → 做一集新的</Link>
          </p>
          <div className="grid sm:grid-cols-3 gap-3 not-prose text-sm">
            {[
              {
                icon: FileText,
                label: '粘贴片段',
                desc: '把小说正文或大纲粘贴到文本框，至少 50 字。适合已有现成文稿的用户。',
              },
              {
                icon: Upload,
                label: '上传小说',
                desc: '上传 txt / docx / pdf 文件，系统自动解析章节与人物（与粘贴片段共用表单）。',
              },
              {
                icon: Type,
                label: '主题生成',
                desc: '只输入 4 字以上的故事主题（如「聊斋·聂小倩」），AI 自动扩写剧情。',
              },
            ].map((m) => (
              <div key={m.label} className="card p-4">
                <m.icon className="w-6 h-6 text-cinnabar-600 mb-2" />
                <div className="font-semibold text-ink-900 mb-1">{m.label}</div>
                <p className="text-ink-600 text-xs leading-relaxed">{m.desc}</p>
              </div>
            ))}
          </div>
          <p className="text-sm mt-2">提交前还需选择：</p>
          <ul className="text-sm list-disc list-inside space-y-1">
            <li><strong>作品标题</strong>：便于在工作台识别（可留空，系统自动命名）</li>
            <li><strong>题材</strong>：古风 / 现代 / 甜宠 / 悬疑 / 玄幻等</li>
            <li><strong>画风</strong>：如古风 3D 国漫、现代电影感、甜宠半二次元等</li>
            <li><strong>集数</strong>：Free 用户固定 1 集；Pro 用户最多 10 集</li>
            <li><strong>语言</strong>：中文 / English / 日本語 / 한국어（影响配音与字幕）</li>
          </ul>
          <p className="text-sm">确认配额与费用无误后，点击「✨ 开始做漫剧」提交任务。</p>

          <h3 className="font-semibold text-ink-900 mt-6">5.2 简易模式（爆款模板）</h3>
          <p className="text-sm">
            路径：
            <Link href="/dashboard/new/wizard" className="text-cinnabar-700 underline ml-1">
              爆款模板 · 简易模式
            </Link>
          </p>
          <p className="text-sm">
            从预设爆款模板中选一个（已配置好画风、镜头节奏、字幕样式与 BGM），
            输入主角名字即可一键开拍。适合不想调参数、想快速出片的用户。
          </p>

          <h3 className="font-semibold text-ink-900 mt-6">5.3 专业模式</h3>
          <p className="text-sm">
            路径：
            <Link href="/dashboard/new/pro" className="text-cinnabar-700 underline ml-1">
              专业模式
            </Link>
          </p>
          <p className="text-sm">
            可精细设置画幅比例（9:16 / 16:9 / 1:1）、分辨率（1080p / 2K / 4K）、帧率、单集时长、
            自定义画风上传等高级参数。适合有短视频运营经验的内容创作者。
          </p>
        </Section>

        <Section id="progress" title="6. 生成进度与六步流程">
          <p className="text-sm">
            提交任务后，系统自动进入流水线。您可在{' '}
            <Link href="/dashboard" className="text-cinnabar-700 underline">
              工作台
            </Link>{' '}
            或作品详情页查看实时进度（页面每几秒自动刷新）。
          </p>
          <p className="text-sm">任务状态说明：</p>
          <ul className="text-sm list-disc list-inside space-y-1">
            <li><strong>排队中</strong>：等待系统分配算力</li>
            <li><strong>渲染中</strong>：流水线正在执行（通常需数分钟至十几分钟）</li>
            <li><strong>已完成</strong>：成片可预览与下载</li>
            <li><strong>失败</strong>：查看错误信息与日志，可重新提交</li>
          </ul>

          <h3 className="font-semibold text-ink-900 mt-4">六步流水线</h3>
          <div className="grid sm:grid-cols-2 gap-3 not-prose">
            {PIPELINE_STEPS.map((s) => (
              <div key={s.n} className="flex gap-3 card p-4">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-cinnabar-600 text-white font-serif flex items-center justify-center text-sm">
                  {s.n}
                </div>
                <div>
                  <div className="font-semibold text-ink-900 text-sm">{s.title}</div>
                  <p className="text-xs text-ink-600 mt-0.5 leading-relaxed">{s.desc}</p>
                </div>
              </div>
            ))}
          </div>
          <Tip>
            无需手动干预——全程自动执行。若开启「逐步确认」模式（专业设置），
            某步完成后会暂停等待您点击确认再继续。
          </Tip>
        </Section>

        <Section id="job" title="7. 作品详情页">
          <p className="text-sm">
            在工作台点击任务标题进入详情页。页面包含：
          </p>
          <ul className="text-sm list-disc list-inside space-y-1">
            <li><strong>进度条与六步 Stepper</strong>：当前执行到哪一步</li>
            <li><strong>100 分工业评分</strong>：Tech / Visual / Narrative / Genre 四大维度</li>
            <li><strong>视频预览与下载</strong>：完成后可直接播放并下载 MP4</li>
            <li><strong>原文片段</strong>：您提交的小说或主题文本</li>
            <li><strong>渲染日志</strong>：排查问题时查看详细执行记录</li>
          </ul>

          <h3 className="font-semibold text-ink-900 mt-4">完成后可执行的操作</h3>
          <ul className="text-sm list-disc list-inside space-y-1">
            <li>
              <strong>人工确认放行</strong>：您对成片满意后点击确认（可选，用于内部审核流程）
            </li>
            <li>
              <strong>一键重绘</strong>：对整体效果不满意时，重新排队生成（会再次消耗配额/余额）
            </li>
            <li>
              <strong>取消任务</strong>：仅在「排队中」或「渲染中」可用
            </li>
          </ul>

          <p className="text-sm mt-2">详情页还提供三个子功能入口：</p>
          <div className="flex flex-wrap gap-2 not-prose text-sm">
            <span className="badge bg-ink-100 text-ink-700 px-3 py-1.5">🎬 镜头与 7 维评分</span>
            <span className="badge bg-ink-100 text-ink-700 px-3 py-1.5">🗂 版本中心</span>
            <span className="badge bg-ink-100 text-ink-700 px-3 py-1.5">📤 多平台导出</span>
          </div>
        </Section>

        <Section id="shots" title="8. 镜头质检与 7 维评分">
          <p className="text-sm">
            进入「镜头与 7 维评分」页面，可逐镜查看每个画面的质量诊断。
            7 个维度各 0–10 分：
          </p>
          <ul className="text-sm grid sm:grid-cols-2 gap-1">
            <li>• 结构（构图是否合理）</li>
            <li>• 风格（是否与选定画风一致）</li>
            <li>• 细节（服饰、道具等精细度）</li>
            <li>• 画质（清晰度与噪点）</li>
            <li>• 色彩（色调是否协调）</li>
            <li>• 无崩坏（面部、手部是否正常）</li>
            <li>• 意图（是否贴合剧本描述）</li>
          </ul>
          <p className="text-sm mt-2">针对单个镜头，您可以：</p>
          <ul className="text-sm list-disc list-inside space-y-1">
            <li><strong>重绘</strong>：重新生成该镜头画面</li>
            <li><strong>局部修复</strong>：对崩坏区域（如手部）进行 inpaint 修复</li>
            <li><strong>通过</strong>：标记该镜头质检合格</li>
          </ul>
          <Tip>
            系统会在交付前自动跑分并修复。人工复核适合对个别镜头有精细要求的创作者。
          </Tip>
        </Section>

        <Section id="versions" title="9. 版本中心">
          <p className="text-sm">
            每次重绘或重大修改都会生成新的<strong>版本快照</strong>，保存在版本中心。
            您可以：
          </p>
          <ul className="text-sm list-disc list-inside space-y-1">
            <li>对比不同版本之间的画面与文本差异</li>
            <li>查看版本演进时间线</li>
            <li><strong>一键回滚</strong>到历史版本</li>
          </ul>
          <p className="text-sm">
            适合反复打磨同一集、或在多个方向之间切换时使用。
          </p>
        </Section>

        <Section id="export" title="10. 多平台导出">
          <p className="text-sm">
            成片完成后，进入「多平台导出」页面，一次选择多个目标平台：
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 not-prose text-sm">
            {['抖音 9:16', '快手 9:16', '视频号 9:16', '小红书 3:4', 'B 站 16:9', 'YouTube Shorts 9:16'].map(
              (p) => (
                <div key={p} className="card px-3 py-2 text-center text-ink-800">
                  {p}
                </div>
              ),
            )}
          </div>
          <p className="text-sm mt-2">导出选项：</p>
          <ul className="text-sm list-disc list-inside space-y-1">
            <li>开启 <strong>AI 水印 + 账号水印</strong>（合规要求，建议保持开启）</li>
            <li>填写您的平台账号名，水印会自动嵌入</li>
            <li>系统同时生成各平台的<strong>引流文案</strong>（标题、描述、话题标签）</li>
          </ul>
          <p className="text-sm">点击导出后，按平台分别下载对应尺寸的视频文件。</p>
        </Section>

        <Section id="showcase" title="11. 作品广场（示例 + 用户作品）">
          <p className="text-sm">
            打开{' '}
            <Link href="/showcase" className="text-cinnabar-700 underline">
              作品广场
            </Link>
            ，可浏览：
          </p>
          <ul className="text-sm list-disc list-inside space-y-1">
            <li><strong>官方示例</strong>：项目内 R40 实测生成的 4 部样片（聊斋 + 西游记），可直接播放</li>
            <li><strong>用户作品</strong>：所有用户成功生成的漫剧会自动公开到广场，供所有人观看</li>
          </ul>
          <Tip>
            您生成的视频在任务「已完成」后会自动出现在作品广场；邮箱会做脱敏显示以保护隐私。
          </Tip>
        </Section>

        <Section id="templates" title="12. 爆款模板库">
          <p className="text-sm">
            顶部导航「模板库」(
            <Link href="/templates" className="text-cinnabar-700 underline">
              /templates
            </Link>
            ) 展示各题材的示例主题与推荐配置。您可以：
          </p>
          <ul className="text-sm list-disc list-inside space-y-1">
            <li>浏览不同题材（古风、甜宠、悬疑等）的样例与说明</li>
            <li>点击「用这个主题创作」直接跳转到创作页并预填题材</li>
          </ul>
          <p className="text-sm">
            简易模式（
            <Link href="/dashboard/new/wizard" className="text-cinnabar-700 underline">
              爆款模板向导
            </Link>
            ）则提供完整的镜头 + BGM + 字幕套餐，一键开拍。
          </p>
        </Section>

        <Section id="library" title="13. 资产库">
          <p className="text-sm">
            「资产库」(
            <Link href="/library" className="text-cinnabar-700 underline">
              /library
            </Link>
            ) 汇总系统可用的视觉资源，分五个标签页：
          </p>
          <ul className="text-sm list-disc list-inside space-y-1">
            <li><strong>角色</strong>：人物设定与 canonical 参考图</li>
            <li><strong>场景</strong>：室内外场景背景</li>
            <li><strong>表情</strong>：喜 / 怒 / 哀 / 惊等情绪库</li>
            <li><strong>动作</strong>：站立、行走、打斗等姿态模板</li>
            <li><strong>服饰</strong>：朝代 / 季节 / 场合换装预设</li>
          </ul>
          <p className="text-sm">
            普通用户一般无需手动管理资产库——创建任务时系统会自动选用。
            进阶用户可在此了解可用资源，便于专业模式下调参。
          </p>
        </Section>

        <Section id="batch" title="14. 批量转绘">
          <p className="text-sm">
            「批量转绘」(
            <Link href="/batch" className="text-cinnabar-700 underline">
              /batch
            </Link>
            ) 适合已有分镜图或漫画图、希望统一转成指定画风的用户：
          </p>
          <ol className="text-sm list-decimal list-inside space-y-1">
            <li>上传一张或多张图片</li>
            <li>创建批次并选择目标画风</li>
            <li>点击「运行」，等待转绘完成</li>
            <li>对不满意的单张可单独「重绘」</li>
            <li>全部完成后「打包下载」ZIP</li>
          </ol>
          <Warn>
            批量转绘与「从小说生成漫剧」是独立功能。若您要从文字开始创作，请使用第 5 节的创作入口。
          </Warn>
        </Section>

        <Section id="faq" title="15. 常见问题">
          <div className="space-y-4 not-prose">
            {[
              {
                q: '生成一集大概要多久？',
                a: '通常 5–20 分钟，取决于集数、分辨率与当前队列负载。详情页进度条与日志会实时更新。',
              },
              {
                q: 'Free 用户今天配额用完了怎么办？',
                a: '等到次日零点配额重置，或前往价格页充值任意金额升级 Pro，即可解除每日限制。',
              },
              {
                q: '粘贴片段最少多少字？',
                a: '至少 50 字。主题生成模式只需 4 字以上的主题描述。',
              },
              {
                q: '成片的画质和尺寸是多少？',
                a: '默认 9:16 竖屏、1080p、24fps。专业模式可选 16:9、1:1、2K、4K 等。',
              },
              {
                q: '可以上传自己的小说文件吗？',
                a: '可以。创作页「上传小说」标签支持 txt、docx、pdf 格式。',
              },
              {
                q: '评分不到 95 分会怎样？',
                a: '系统会自动触发 Multi-VLM 修复流程，最多重试 2 次，达标后才交付。您也可在镜头页手动重绘。',
              },
              {
                q: '生成的内容可以商用吗？',
                a: '请确保输入素材为您自有或已获授权。产出均带 AIGC 标识，发布到各平台时请遵守当地法规与平台规则。',
              },
              {
                q: '任务失败了会扣费吗？',
                a: '失败任务通常不会保留扣费；排队或渲染中取消会按比例退款。具体以工作台显示的余额变化为准。',
              },
            ].map((item) => (
              <details key={item.q} className="card p-4 group">
                <summary className="flex items-start gap-2 cursor-pointer font-semibold text-ink-900 list-none">
                  <HelpCircle className="w-5 h-5 text-cinnabar-600 flex-shrink-0 mt-0.5" />
                  <span>{item.q}</span>
                </summary>
                <p className="text-sm text-ink-600 mt-3 ml-7 leading-relaxed">{item.a}</p>
              </details>
            ))}
          </div>
        </Section>
      </div>

      {/* 底部 CTA */}
      <div className="mt-16 card p-8 text-center">
        <Film className="w-10 h-10 text-cinnabar-600 mx-auto mb-3" />
        <h2 className="font-serif text-2xl text-ink-900 mb-2">准备好创作了吗？</h2>
        <p className="text-ink-600 mb-6 text-sm">
          点开就用 · 自动赠 100 元体验金 · Free 用户每天 20 集免费
        </p>
        <div className="flex flex-wrap gap-3 justify-center">
          <Link href="/signup" className="btn-primary">
            <Sparkles className="w-4 h-4 mr-2" /> 免费注册
          </Link>
          <Link href="/dashboard/new" className="btn-secondary">
            <Wand2 className="w-4 h-4 mr-2" /> 立即创作
          </Link>
          <Link href="/quality" className="btn-ghost text-sm">
            <Award className="w-4 h-4 mr-1" /> 了解评分方法
          </Link>
        </div>
      </div>
    </div>
  );
}
