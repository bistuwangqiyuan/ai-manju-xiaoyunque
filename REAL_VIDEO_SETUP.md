# 真实视频生成管线配置说明

用户创建任务时，**只有**在 SCF 云函数 `xyq-api` 开启真实管线后，才会走火山 Manju Agent / HappyHorse，**不会**再静默返回首页示例视频。

## 判断是否已开启

```bash
curl https://cursoraicode-5g67ezfl8a1891da-1300352403.ap-shanghai.app.tcloudbase.com/api/health
```

期望返回：

```json
{
  "real_video_mode": true,
  "mock_worker": false,
  "manju_configured": true,
  "cos_configured": true,
  "happyhorse_configured": true
}
```

创建任务后 `pipeline_version` 应为 `v10-manju-agent` 或 `v10-happyhorse-i2v`，**不是** `v6-mock`。

## SCF 环境变量（CloudBase 控制台 → 云函数 xyq-api → 环境变量）

| 变量 | 必填 | 说明 |
|------|------|------|
| `REAL_VIDEO_MODE` | 是 | 固定填 `manju` |
| `VOLC_ACCESS_KEY` | 是 | 火山引擎 AK |
| `VOLC_SECRET_KEY` | 是 | 火山引擎 SK |
| `COS_BUCKET` | 是 | `6375-cursoraicode-5g67ezfl8a1891da-1300352403` |
| `COS_REGION` | 是 | `ap-shanghai` |
| `HAPPYHORSE_API_KEY` | 建议 | 阿里百炼 Key，限流/50500 时自动备用 |
| `DASHSCOPE_API_KEY` | 可选 | 与上一项同值即可 |

**不要**再设置 `MOCK_MODE=1`（会误导运维；代码已不再用 mock 创建任务）。

腾讯云 `TENCENTCLOUD_SECRETID/SECRETKEY` 由 SCF 运行时自动注入，用于 COS 读写，无需手写。

## 本地一键部署（密钥只放环境变量，勿提交 git）

```powershell
$env:VOLC_ACCESS_KEY='你的火山AK'
$env:VOLC_SECRET_KEY='你的火山SK'
$env:HAPPYHORSE_API_KEY='sk-你的百炼Key'
python scripts/deploy_cloudfn_slim.py
```

或分步：

```powershell
tcb fn code update xyq-api --dir deploy/cloudfn-slim -e cursoraicode-5g67ezfl8a1891da
# 环境变量在控制台补齐 HAPPYHORSE_API_KEY 后保存
```

## 生成官方示例视频（荀彧 30s 真人写实）

```powershell
$env:HAPPYHORSE_API_KEY='sk-...'
$env:FORCE='1'
$env:FORCE_T2I='1'
python scripts/generate_xunyu_sample.py
```

HappyHorse 单次最长 15s，脚本自动 **两段 15s + ffmpeg 拼接** 为 30s。

## 全链路真实任务 E2E 测试

```powershell
python scripts/verify_e2e_real_video.py
```

需 `test1@139.com` / `123456` 账号，约 10–60 分钟完成一轮 Manju 渲染。
