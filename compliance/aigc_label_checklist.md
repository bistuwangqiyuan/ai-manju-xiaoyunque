# AIGC 标识合规清单（国标 GB/T 45438-2025）

> 法规依据：
> - 《人工智能生成合成内容标识办法》（2025/09 国家网信办正式实施）
> - GB/T 45438-2025《信息技术 人工智能 生成内容标识技术要求》
> - 国家广电总局 2026/04/01《调整微短剧分类分层标准的通知》

每集成片上线前，按本清单逐项核对：

---

## 一、显式标识（人眼可见）

### 1.1 视频角落水印
- [ ] 视频右下角永久显示「AI 生成」文字
- [ ] 字体：思源黑体 CN Bold
- [ ] 字号：36pt（1080P），按比例放大至 4K
- [ ] 颜色：白色 60% 透明 + 黑色描边 2px
- [ ] 位置：距右边缘 30px，距底边 30px
- [ ] 检查命令：
  ```bash
  ffmpeg -i ep01.mp4 -ss 5 -frames:v 1 -y /tmp/check.png
  # 肉眼检视 /tmp/check.png 右下角
  ```

### 1.2 平台显示标签
- [ ] 上传时勾选「AI 生成内容」标签
- [ ] 标题前缀加「【AI】」字样
- [ ] 简介首行声明：「本作品由 AI 全流程生成，仅供创作与娱乐」

### 1.3 片头声明（可选但推荐）
- [ ] ep01 片头 0-2 秒：黑底白字「本剧由 AI 全流程生成」

---

## 二、隐式标识（机器可读）

### 2.1 C2PA Content Credentials
- [ ] mp4 文件内嵌 C2PA v1.4 manifest
- [ ] 包含字段：
  - `creator`：制作主体名
  - `claim_generator`：「Skylark Agent 2.0 / Seedance 2.0 / Veo 3.1 ...」
  - `created`：ISO 8601 时间戳
  - `signature`：制作主体 X.509 证书签名
- [ ] 验证命令：
  ```bash
  c2patool ep01.mp4
  ```

### 2.2 SynthID（Google 输出，Veo 3.1 自动嵌入）
- [ ] Veo 3.1 / Veo upscaler 输出自动包含 SynthID
- [ ] 不需要手动操作，但需保留 Vertex AI 日志以备核查

### 2.3 火山小云雀「AIGC 元数据」（v2026-05 真值流程）
- [ ] **写入时机**：在 **查询任务（`CVSync2AsyncGetResult`）** 请求体的 `req_json`
      字段中传入 JSON 序列化后的 `aigc_meta`，由小云雀在生成结果中落标。
- [ ] **req_json 模板**：
      ```json
      {"aigc_meta": {
          "content_producer":   "<制作主体 18 位 USCC，长度 ≤256>",
          "producer_id":        "<本集唯一 ID, 如 ep01_run20260516>",
          "content_propagator": "<平台分发账号 ID>",
          "propagate_id":       "<传播服务商内部 ID>"
      }}
      ```
- [ ] 查询响应字段 `aigc_meta_tagged=true` 必须落库（`episodes.aigc_meta_tagged`）。
- [ ] 若 `aigc_meta_tagged=false`，复检：**(a)** 字段长度 ≤ 256；
      **(b)** producer_id 真实唯一；**(c)** 再次调用 query 接口重试。
- [ ] **官方验证**：上传打标后视频到
      [人工智能生成合成内容标识服务平台](https://www.gcmark.com/web/index.html#/mark/check/video)
      检测，输出"检测成功"即代表落标。
- [ ] 同时小云雀官方"明水印"（左上"AI生成" + 右下"小云雀AI生成"）由
      `enable_watermark` 字段控制。**商用规则**：本项目关闭官方明水印
      （enable_watermark=false），由本地 ffmpeg 自渲染"AI 生成"角标，
      防止双重水印影响平台审美。

### 2.4 视频元数据 EXIF / Atoms
- [ ] mp4 `udta` 原子嵌入：
  - `©too`：「Skylark Agent 2.0 + Veo 3.1 Hybrid Pipeline v5」
  - `©cmt`：「AI 全流程生成；监制：[姓名]」

---

## 三、平台特定要求

### 3.1 抖音 / 头条系
- [ ] 进入「AI 创作中心」 → 完成「AIGC 创作者认证」
- [ ] 发布时关闭「智能美化」「AI 增强」按钮（避免二次 AIGC 嵌套）
- [ ] 必须勾选「内容由 AI 生成」开关

### 3.2 视频号 / 微信
- [ ] 申请 AIGC 创作者认证
- [ ] 标题禁含「真人」「真实事件」字样
- [ ] 评论区置顶 AIGC 声明

### 3.3 红果短剧
- [ ] 在制作单位资质中勾选「AIGC 制作」
- [ ] 提交红果专项 AIGC 备案表
- [ ] 内容审核加快通道：1-3 个工作日

### 3.4 B 站
- [ ] 发布时选择「AI 内容」标签
- [ ] 简介首行：「本作品由 AI 全流程生成」
- [ ] 国漫频道分区：「国创区 - 国创 PV」

### 3.5 YouTube / TikTok（海外）
- [ ] YouTube：发布时开启「Altered or synthetic content」开关
- [ ] TikTok：「AI-generated」label 必须显式打开
- [ ] 简介英文版加 `#AIGenerated #AIAnimation`

---

## 四、违规自查（每集发布前）

### 4.1 内容审核三必查
- [ ] 是否含血腥镜头（足心锥刺 / 鬼骨化金 → 必须柔化）
- [ ] 是否含性暗示（小倩勾引 → 改为月下相邀）
- [ ] 是否宣扬迷信（妖物必须有明确叙事逻辑）

### 4.2 版权三必查
- [ ] 是否使用了徐克 87 版独创元素（长舌树妖 / 浴桶吻 / 黑山老妖 / 投胎结局 → 一律不得使用）
- [ ] 是否使用了 2011 古天乐版独创元素（中西混合大殿空间 → 已替换为中式 + 树根地宫）
- [ ] BGM 是否走 ElevenLabs Music API（版权干净）—— Suno BGM 仅限 Premier 套餐主题曲
- [ ] Sora 2 API 是否上传了脸照（**禁止**，仅可纯文/图生镜头）

### 4.3 AIGC 标识三必查
- [ ] 显式水印「AI 生成」可见性测试
- [ ] C2PA manifest 验证
- [ ] 小云雀响应 `aigc_meta_tagged=true`

---

## 五、自动化检查脚本

每集发布前执行：

```bash
python scripts/compliance_check.py --episode ep01

# 输出示例：
# ✓ 显式水印检测通过（右下角检出「AI 生成」）
# ✓ C2PA manifest valid，creator/claim_generator/signature 齐全
# ✓ SynthID 检测通过
# ✓ Skylark aigc_meta_tagged=true
# ✓ EXIF udta 元数据齐全
# ✓ 抖音平台 AIGC 标签预演通过
# 总分：6/6 ✅ 可发布
```

> 若任一项失败，必须修复后才能上线。`compliance_check.py` 的实现作为 Shell 5
> 后期管线的一部分，集成在 `post_production` 的最后一道关卡。

---

## 六、应急下架预案

若上线后被平台标记：

1. **5 分钟内** 隔离原始文件 + 备份当前在线版
2. **30 分钟内** 编写下架声明 + 整改方案
3. **24 小时内** 提交整改材料，重新审核

参考案例：2026/01/15 某 AIGC 短剧因未嵌 SynthID 被抖音临时下架，整改 6 小时后恢复。
