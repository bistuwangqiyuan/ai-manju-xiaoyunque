# V10 §7.3 — Subtitle font assets

Drop the following font files here. The ASS subtitle renderer references
them by name, so the filenames may differ — what matters is that the
*font-family* names line up with the ones declared in
`src/shell5_post_production/ass_subtitle.py`.

| Style key       | font-family declared in ASS         | suggested file              | license   |
|-----------------|-------------------------------------|------------------------------|-----------|
| `Default`       | `思源黑体 CN Bold`                   | `SourceHanSansCN-Bold.otf`   | SIL OFL   |
| `Voiceover`     | `思源宋体 CN`                        | `SourceHanSerifCN-Regular.otf`| SIL OFL   |
| `AncientSeal`   | `方正小篆体`                         | `FZXZTK-GB1-0.TTF`           | 方正字库免费版（个人） |
| `AncientKai`    | `方正楷体_GBK`                       | `FZKTK.TTF`                  | 方正字库免费版（个人） |
| `ModernSans`    | `思源黑体 CN Bold`                   | (same as Default)            | SIL OFL   |
| `ModernRound`   | `阿里巴巴普惠体 R`                   | `AlibabaPuHuiTi-Regular.otf` | 免费商用 |
| `DanmuTop`      | `思源黑体 CN`                        | `SourceHanSansCN-Regular.otf`| SIL OFL   |
| `DanmuRoll`     | `思源黑体 CN`                        | (same as DanmuTop)           | SIL OFL   |

## Installation on the worker

The container image install step (see `deploy/cn-volc-vefaas/Dockerfile.vefaas`)
should run:

```bash
mkdir -p /usr/share/fonts/truetype/v10
cp assets/fonts/*.ttf assets/fonts/*.otf /usr/share/fonts/truetype/v10/
fc-cache -f
```

so that ffmpeg + libass can find them at compose time.

## Local development

On Windows, the existing `C:\Windows\Fonts` resolution works for the
default font; for the four ancient/modern variants, install them via
double-click. On macOS, drop into `~/Library/Fonts`.
