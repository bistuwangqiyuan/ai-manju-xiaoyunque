"""Batch 转绘 (image-to-image redraw) subsystem.

Requirement doc §12 转绘模型使用需求:
    - 多文件上传、批量转绘、批量参数配置、批量结果导出
    - 图像解析、意图对齐、约束提取、多模态融合
    - 结构稳定性 / 细节增强 / 局部编辑
    - 自动评估 + 自我修正闭环
    - 版本管理 (回滚 / 对比 / 追溯)
"""

from .params import RedrawParams, MultiModalRefs
from .engine import RedrawEngine, RedrawResult
from .quality_loop import run_quality_loop
from .exporter import export_batch_zip

__all__ = [
    "RedrawParams",
    "MultiModalRefs",
    "RedrawEngine",
    "RedrawResult",
    "run_quality_loop",
    "export_batch_zip",
]
