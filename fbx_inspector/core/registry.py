"""插件注册表(与 Maya 无关)。

解码器、可视化器、校验器、配置档都通过这里的注册表按 ``id`` 登记与查找。
既支持装饰器登记类,也支持直接登记实例;上层工作室的自定义插件只需在导入时
调用一次 ``register_*`` 即可被发现。
"""

from __future__ import annotations

from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class Registry(Generic[T]):
    """一个按字符串 id 索引的简单注册表。"""

    def __init__(self, kind: str) -> None:
        self._kind = kind  # 仅用于错误信息,如 "decoder"
        self._items: dict[str, T] = {}

    def register(self, item_id: str, item: T, *, overwrite: bool = False) -> T:
        if not overwrite and item_id in self._items:
            raise KeyError(f"{self._kind} id {item_id!r} 已存在;如需覆盖请传 overwrite=True")
        self._items[item_id] = item
        return item

    def get(self, item_id: str) -> T:
        try:
            return self._items[item_id]
        except KeyError:
            raise KeyError(f"未注册的 {self._kind}:{item_id!r}") from None

    def ids(self) -> list[str]:
        return sorted(self._items)

    def all(self) -> dict[str, T]:
        return dict(self._items)


# 四类全局注册表。存放的通常是"可调用的工厂/类"或"实例",由各层自行约定。
DECODERS: Registry = Registry("decoder")
VISUALIZERS: Registry = Registry("visualizer")
VALIDATORS: Registry = Registry("validator")
PROFILES: Registry = Registry("profile")


def register_profile(profile: object, *, overwrite: bool = False) -> object:
    """登记一个配置档实例(要求其有 ``id`` 属性)。可作装饰器用于工厂函数。

    ``overwrite=True`` 便于插件热重载时覆盖同 id 的旧配置档。
    """
    pid = getattr(profile, "id", None)
    if not isinstance(pid, str):
        raise TypeError("profile 必须带有字符串属性 id")
    PROFILES.register(pid, profile, overwrite=overwrite)
    return profile


def _make_class_decorator(reg: Registry) -> Callable[[str], Callable[[type], type]]:
    """生成一个"按 id 登记类"的装饰器工厂。"""

    def decorator(item_id: str) -> Callable[[type], type]:
        def wrap(cls: type) -> type:
            reg.register(item_id, cls)
            return cls

        return wrap

    return decorator


# 用法:@decoder("scalar_from_component") class ScalarFromComponent(Decoder): ...
decoder = _make_class_decorator(DECODERS)
visualizer = _make_class_decorator(VISUALIZERS)
validator = _make_class_decorator(VALIDATORS)
