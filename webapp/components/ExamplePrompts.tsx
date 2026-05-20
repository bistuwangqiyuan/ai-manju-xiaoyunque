'use client';

/**
 * 内置 R30-R40 实测可生成的示例 prompt。
 * 用户点击 → 填入 textarea。
 */
import { useState } from 'react';

export interface ExamplePrompt {
  title: string;
  source: string;
  prompt: string;
  durationPreset?: '～15s' | '～30s';
  ratio?: '9:16' | '16:9';
  score?: string;
}

export const EXAMPLES: ExamplePrompt[] = [
  {
    title: '兰若投宿 · 月光镜像',
    source: '聊斋·聂小倩 (蒲松龄, 公版)',
    score: 'R40 评分 96.87/100',
    prompt:
      '【0-2s 锚定】超大特写正面镜头，宁采臣面部占画面八成，目光微垂，烛火在瞳孔中倒映成一豆暖光。背景虚化兰若寺木格窗棂，月白冷青调主导。Unreal5 路径追踪渲染皮肤次表面散射。\n\n【2-6s 主体】中景跟拍，宁采臣青色长衫执灯走入兰若寺供堂，供桌上铜镜泛冷月光辉，灯火摇曳投影于壁画之上。镜头稳定追踪。\n\n【6-10s 深化】浅景深推近至胸上中景，宁采臣放下书箱，回望铜镜，镜中映出空堂残烛与他单薄的背影。\n\n【10-13s 悬念铺】镜头缓慢绕至铜镜近景，镜面深处似有微动，宁采臣眉头微皱，烛火忽地一颤。\n\n【13-15s 钩子定格】铜镜中突然浮出一道朦胧白衣身影，画面骤然定格，frozen gesture。',
  },
  {
    title: '月下倩影 · 朱砂痣',
    source: '聊斋·聂小倩 (蒲松龄, 公版)',
    score: 'R40 评分 96.47/100 (v3 prompt)',
    prompt:
      '【0-2s 锚定】超大特写正面镜头，聂小倩面部占画面八成，杏眼缓缓睁开，浅蓝灰瞳孔泛冷月微光，眉间一点朱砂痣 #C5283D 直径 3mm 居中黄金分割，肌肤月白透青。镜头零移动，f1.2 极浅景深。色板严守冷青+月白+朱砂红三调。\n\n【2-6s 主体】机位贴地缓慢横移，聂小倩白衣襦裙浅粉缎带于纯月光下款步前行，水袖拂过冷青石栏。回廊烛火全数熄灭仅余月光独照。\n\n【6-10s 深化】镜头推近至中近景，聂小倩侧首回眸，眼波流转含怨含怜，朱砂痣冷月映照下殷红渐亮如殷血。\n\n【10-13s 悬念铺】聂小倩自袖中取出一袋古铜金钱币，双手奉于身前。月光骤然一暗回廊深处暗影微动。\n\n【13-15s 钩子定格】金币崩解为月白光尘，朱砂痣在逆光中亮如孤星，整张面部仅朱砂痣亮红，余皆冷青剪影。frozen gesture 定格。',
  },
  {
    title: '剑光出鞘 · 老妪剪影',
    source: '聊斋·聂小倩 (蒲松龄, 公版)',
    score: 'R40 评分 97.10/100 ⭐ (v3 face-persistent)',
    prompt:
      '【0-2s 锚定】超近大特写，雨后天青清晨，4K 大特写浅景深推镜锁定燕赤霞面部正面：30 岁亚裔道士剑客，右眉骨浅疤清晰可见，眼神刚毅沉稳目光微垂，皮肤冷青调月白侧光勾勒轮廓，朱砂红披风一角镜头边缘微浮。\n\n【2-6s 主体】镜头缓缓拉远至中景跟拍，镜头始终保持燕赤霞 3/4 侧脸于画面右黄金分割点，深墨色道袍随步伐摆动，暗红披风在身后舒展，腰间褐色革囊随胯部节奏轻晃。\n\n【6-10s 深化】镜头围绕燕赤霞做半圆慢摇至略仰角中近景正面 3/4，他俯身查看友人脉象，眉骨疤痕在月白侧光下明暗交替，指尖凝住于友人腕脉的刹那友人手指轻微抽搐，燕赤霞眉头骤然紧锁。\n\n【10-13s 悬念铺】镜头不离燕赤霞 3/4 侧脸，他转向窗外，窗外远景虚焦浮出兰若寺剪影。\n\n【13-15s 钩子定格】剑骤然出鞘，一道青蓝剑光自下而上划过画面前景，燕赤霞侧脸 3/4 仍占画面左侧前景中近景，画面右侧远处月白粉墙浮出一道佝偻老妪剪影，frozen gesture。',
  },
];

export function ExamplePrompts({
  onPick,
}: {
  onPick: (p: ExamplePrompt) => void;
}) {
  const [active, setActive] = useState<number | null>(null);
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-3">
      {EXAMPLES.map((ex, i) => (
        <button
          key={i}
          onClick={() => {
            setActive(i);
            onPick(ex);
          }}
          className={`text-left p-4 rounded-2xl border transition-all ${
            active === i
              ? 'border-accent bg-white shadow-sm'
              : 'border-line bg-white/60 hover:bg-white hover:border-ink2'
          }`}
        >
          <div className="text-sm font-medium text-ink">{ex.title}</div>
          <div className="text-xs text-ink2 mt-1">{ex.source}</div>
          {ex.score && (
            <div className="text-xs text-accent mt-2 font-medium">{ex.score}</div>
          )}
        </button>
      ))}
    </div>
  );
}
