"""校验器抽象基类(与 Maya 无关)。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..core.types import DecodedData, Issue


class Validator(ABC):
    """所有校验器的基类:吃一份 DecodedData,吐一组 Issue。"""

    #: 该校验器最多报告多少条组件级问题,避免坏数据刷屏。-1 表示不限。
    max_issues: int = 200

    @abstractmethod
    def validate(self, data: DecodedData) -> list[Issue]:
        raise NotImplementedError
