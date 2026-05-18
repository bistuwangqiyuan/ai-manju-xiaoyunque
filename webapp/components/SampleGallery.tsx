'use client';

/**
 * SampleGallery — 真实 R40 已生成样片画廊。
 *
 * 用户点击 "用此 prompt 生成同款" → 复制到上方表单 + 滚动到表单。
 * 视频 muted autoplay loop 静默播放，hover/tap 展开声音控制。
 */
import { useState } from 'react';

export interface Sample {
  src: string;        // /samples/xxx.mp4 (in public/)
  poster: string;     // /samples/xxx.jpg
  title: string;
  source: string;
  score: number;
  scoreLabel: string;
  taskId: string;
  prompt: string;
  promptVersion: 'v2' | 'v3';
  badge?: string;     // "⭐ 最高分" etc.
}

export const SAMPLES: Sample[] = [
  {
    src: '/samples/nie03_yan_chixia.mp4',
    poster: '/samples/nie03_yan_chixia.jpg',
    title: '剑光出鞘 · 老妪剪影',
    source: '聊斋·聂小倩',
    score: 97.10,
    scoreLabel: 'R40 实测 · 全集最高分',
    taskId: '13001907883391099534',
    promptVersion: 'v3',
    badge: '⭐ 97.10',
    prompt:
      '【0-2s 锚定】超近大特写，雨后天青清晨，4K 大特写浅景深推镜锁定燕赤霞面部正面：30 岁亚裔道士剑客，右眉骨浅疤清晰可见，眼神刚毅沉稳目光微垂，皮肤冷青调月白侧光勾勒轮廓，朱砂红披风一角镜头边缘微浮。\n\n【2-6s 主体】镜头缓缓拉远至中景跟拍，镜头始终保持燕赤霞 3/4 侧脸于画面右黄金分割点，深墨色道袍随步伐摆动，暗红披风在身后舒展，腰间褐色革囊随胯部节奏轻晃。\n\n【6-10s 深化】镜头围绕燕赤霞做半圆慢摇至略仰角中近景正面 3/4，他俯身查看友人脉象，眉骨疤痕在月白侧光下明暗交替，指尖凝住于友人腕脉的刹那友人手指轻微抽搐，燕赤霞眉头骤然紧锁。\n\n【10-13s 悬念铺】镜头不离燕赤霞 3/4 侧脸，他转向窗外，窗外远景虚焦浮出兰若寺剪影。\n\n【13-15s 钩子定格】剑骤然出鞘，一道青蓝剑光自下而上划过画面前景，画面右侧远处月白粉墙浮出一道佝偻老妪剪影，frozen gesture。',
  },
  {
    src: '/samples/nie01_lanruosi.mp4',
    poster: '/samples/nie01_lanruosi.jpg',
    title: '兰若投宿 · 月光镜像',
    source: '聊斋·聂小倩',
    score: 96.87,
    scoreLabel: 'R40 实测',
    taskId: '11698989232001516248',
    promptVersion: 'v2',
    prompt:
      '【0-2s 锚定】超大特写正面镜头，宁采臣面部占画面八成，目光微垂，烛火在瞳孔中倒映成一豆暖光。背景虚化兰若寺木格窗棂，月白冷青调主导。Unreal5 路径追踪渲染皮肤次表面散射。\n\n【2-6s 主体】中景跟拍，宁采臣青色长衫执灯走入兰若寺供堂，供桌上铜镜泛冷月光辉，灯火摇曳投影于壁画之上。镜头稳定追踪。\n\n【6-10s 深化】浅景深推近至胸上中景，宁采臣放下书箱，回望铜镜，镜中映出空堂残烛与他单薄的背影。\n\n【10-13s 悬念铺】镜头缓慢绕至铜镜近景，镜面深处似有微动，宁采臣眉头微皱，烛火忽地一颤。\n\n【13-15s 钩子定格】铜镜中突然浮出一道朦胧白衣身影，画面骤然定格，frozen gesture。',
  },
  {
    src: '/samples/nie02_appears.mp4',
    poster: '/samples/nie02_appears.jpg',
    title: '月下倩影 · 朱砂痣',
    source: '聊斋·聂小倩',
    score: 96.47,
    scoreLabel: 'R40 实测',
    taskId: '6730696300096597097',
    promptVersion: 'v3',
    prompt:
      '【0-2s 锚定】超大特写正面镜头，聂小倩面部占画面八成，杏眼缓缓睁开，浅蓝灰瞳孔泛冷月微光，眉间一点朱砂痣 #C5283D 直径 3mm 居中黄金分割，肌肤月白透青。镜头零移动，f1.2 极浅景深。色板严守冷青+月白+朱砂红三调。\n\n【2-6s 主体】机位贴地缓慢横移，聂小倩白衣襦裙浅粉缎带于纯月光下款步前行，水袖拂过冷青石栏。回廊烛火全数熄灭仅余月光独照。\n\n【6-10s 深化】镜头推近至中近景，聂小倩侧首回眸，眼波流转含怨含怜，朱砂痣冷月映照下殷红渐亮如殷血。\n\n【10-13s 悬念铺】聂小倩自袖中取出一袋古铜金钱币，双手奉于身前。月光骤然一暗回廊深处暗影微动。\n\n【13-15s 钩子定格】金币崩解为月白光尘，朱砂痣在逆光中亮如孤星，整张面部仅朱砂痣亮红，余皆冷青剪影。frozen gesture。',
  },
  {
    src: '/samples/xiyou01_immortal_stone.mp4',
    poster: '/samples/xiyou01_immortal_stone.jpg',
    title: '花果山仙石异变',
    source: '西游记·石猴出世',
    score: 93.19,
    scoreLabel: 'R23 实测',
    taskId: 'xiyou-r23-ep01',
    promptVersion: 'v2',
    prompt:
      '【0-2s 锚定】超大特写镜头，花果山顶仙石占画面八成，灵气流转，石身青黑泛金光斑，云雾缭绕。日月精华聚于石顶。\n\n【2-6s 主体】镜头缓拉远至中景，全景仙石矗立东海花果山巅，惊涛拍岸，万年灵气环绕，光辉透云照地。\n\n【6-10s 深化】镜头推近至仙石表面纹理特写，金色裂纹缓慢延展，仙气流动可见。\n\n【10-13s 悬念铺】裂纹骤然加深，仙石轻颤，远处雷云聚拢。\n\n【13-15s 钩子定格】仙石上方一道金光骤然冲破云层，画面定格于裂纹与金光同框瞬间，frozen gesture。',
  },
  {
    src: '/samples/nie03_lanruosi_v1.mp4',
    poster: '/samples/nie03_lanruosi_v1.jpg',
    title: '剑光出鞘 · v1 对比',
    source: '聊斋·聂小倩 · R13 旧版',
    score: 91.83,
    scoreLabel: 'R13 旧版（对比展示）',
    taskId: 'r13-ep03',
    promptVersion: 'v2',
    prompt:
      '【0-2s 锚定·面部超近大特写】雨后天青清晨，4K大特写浅景深推镜锁定燕赤霞面部：30岁亚裔道士剑客，右眉骨浅疤清晰可见，眼神刚毅沉稳，目光微垂。\n\n【2-6s 主体·中景跟拍】镜头缓缓拉远至中景跟拍，燕赤霞推开客栈木门步入榻房。\n\n【6-10s 深化·浅景深推镜】镜头围绕燕赤霞做半圆慢摇至略仰角中近景，他俯身查看友人脉象。\n\n【10-13s 悬念铺·广角慢摇】镜头脱离室内向窗外慢摇大广角，雨后天青苍穹下远景浮出兰若寺剪影。\n\n【13-15s 钩子定格·极端逆光剪影】剑骤然出鞘，一道青蓝剑光自下而上划过夜空。',
  },
];

export function SampleGallery({
  onPick,
}: {
  onPick: (sample: Sample) => void;
}) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
      {SAMPLES.map((s, i) => (
        <SampleCard
          key={s.taskId}
          sample={s}
          open={openIndex === i}
          onToggle={() => setOpenIndex(openIndex === i ? null : i)}
          onPick={() => onPick(s)}
        />
      ))}
    </div>
  );
}

function SampleCard({
  sample,
  open,
  onToggle,
  onPick,
}: {
  sample: Sample;
  open: boolean;
  onToggle: () => void;
  onPick: () => void;
}) {
  return (
    <div className="group relative rounded-2xl overflow-hidden border border-line bg-black aspect-[9/16]">
      <video
        src={sample.src}
        poster={sample.poster}
        muted
        loop
        playsInline
        autoPlay
        preload="metadata"
        className="w-full h-full object-cover"
      />
      {/* score badge */}
      <div className="absolute top-2 left-2 inline-flex items-center gap-1 h-6 px-2 rounded-full bg-black/70 backdrop-blur text-white text-xs font-medium">
        {sample.badge || `${sample.score.toFixed(2)}/100`}
      </div>
      <div className="absolute top-2 right-2 inline-flex items-center h-6 px-2 rounded-full bg-white/85 backdrop-blur text-ink text-[10px] font-medium">
        {sample.promptVersion}
      </div>
      {/* bottom overlay */}
      <div className="absolute inset-x-0 bottom-0 p-3 bg-gradient-to-t from-black/85 to-transparent text-white">
        <div className="text-sm font-medium truncate">{sample.title}</div>
        <div className="text-[11px] text-white/80 truncate">{sample.source}</div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onPick();
          }}
          className="mt-2 w-full h-8 rounded-full bg-white text-ink text-xs font-medium hover:bg-bg active:scale-95 transition"
        >
          用此 prompt 生成同款 →
        </button>
      </div>
    </div>
  );
}
