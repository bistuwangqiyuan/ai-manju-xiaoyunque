"""Advanced intelligence (requirement doc §9).

- continuation: 剧情续写
- style_transfer: 风格迁移 (日系/国漫/写实/二次元)
- interaction_logic: 角色互动逻辑 自动联动
"""

from .continuation import continue_story
from .style_transfer import restyle_video
from .interaction_logic import build_interaction_graph

__all__ = [
    "continue_story",
    "restyle_video",
    "build_interaction_graph",
]
