# -*- coding: utf-8 -*-
"""GIF 调整选项数据模型模块。

定义 GIF 调整工具可用的配置选项。
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class GifAdjustmentOptions:
    """GIF 调整配置数据类。

    Attributes:
        cover_frame_index: 作为首帧显示的帧索引（从 0 开始），``None`` 表示保持原首帧。
        speed_factor: 播放速度倍数，大于 0，数值越大播放越快。
        loop: 循环次数，``0`` 表示无限循环，``None`` 表示保持原值。
        trim_start: 截取起始帧索引（包含），``None`` 表示从第一帧开始。
        trim_end: 截取结束帧索引（包含），``None`` 表示到最后一帧。
        drop_every_n: 每隔多少帧保留一帧，``1`` 表示不跳帧。
        reverse_order: 是否反转帧顺序。
    """

    cover_frame_index: Optional[int] = None
    speed_factor: float = 1.0
    loop: Optional[int] = None
    trim_start: Optional[int] = None
    trim_end: Optional[int] = None
    drop_every_n: int = 1
    reverse_order: bool = False


__all__ = ["GifAdjustmentOptions"]


