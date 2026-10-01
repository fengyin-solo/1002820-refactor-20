"""树木支撑的共用判定：支撑材料、检查日期与稳固情况只在这里算一遍。

登记松动、加固处理、拆除支撑三个动作，以及其它模块读取支撑口径，都统一走本模块，
保证同一株树在任何入口看到的支撑材料、检查日期、稳固情况都来自同一份算法。

这里只放纯函数，不依赖数据仓库，便于在初始化、动作流转、外部复用时直接调用。
"""
from __future__ import annotations

from typing import Any

# 支撑状态的允许序列与终态：任何入口都以此为准，不再各写一份。
STATUS_ORDER = ["稳固", "松动", "损坏", "已拆除"]
DEFAULT_STATUS = STATUS_ORDER[0]
REMOVED_STATUS = STATUS_ORDER[-1]
# 需要关注的异常稳固情况：松动、损坏。
ABNORMAL_STATUSES = {"松动", "损坏"}

# 三个动作统一映射到目标支撑状态。
ACTION_STATUS = {
    "登记松动": "松动",
    "加固处理": "稳固",
    "拆除支撑": REMOVED_STATUS,
}

# 支撑材料缺省时的回退字段；检查日期缺省时回退到安装日期。
MATERIAL_FALLBACK_FIELDS = ("支撑方式",)
CHECK_DATE_FIELDS = ("检查日期", "安装日期")
MATERIAL_FIELD = "支撑材料"
CHECK_DATE_FIELD = "检查日期"
STABILITY_FIELDS = ("稳固情况", "支撑状态")


def clean_text(value: Any) -> str:
    """把提交值规整成去掉首尾空白的字符串；None / 空值统一成空串。"""
    if value is None:
        return ""
    return str(value).strip()


def normalize_status(status: Any) -> str:
    """把任意来源的状态收敛到允许序列里；无法识别时按初始稳固处理。"""
    text = clean_text(status)
    return text if text in STATUS_ORDER else DEFAULT_STATUS


def resolve_material(entry: dict[str, Any]) -> str:
    """支撑材料唯一取值口径：优先登记的材料，缺省时回退到支撑方式。"""
    material = clean_text(entry.get(MATERIAL_FIELD))
    if material:
        return material
    for field in MATERIAL_FALLBACK_FIELDS:
        fallback = clean_text(entry.get(field))
        if fallback:
            return fallback
    return ""


def resolve_check_date(entry: dict[str, Any]) -> str:
    """检查日期唯一取值口径：优先检查日期，缺省时回退到安装日期。"""
    for field in CHECK_DATE_FIELDS:
        date = clean_text(entry.get(field))
        if date:
            return date
    return ""


def is_pending(status: str) -> bool:
    """未拆除的支撑都需要持续跟进；拆除后不再待处理。"""
    return status != REMOVED_STATUS


def is_abnormal(status: str) -> bool:
    """松动、损坏属于异常稳固情况；稳固、已拆除不算异常。"""
    return status in ABNORMAL_STATUSES


def evaluate(entry: dict[str, Any], status: str) -> dict[str, Any]:
    """按一套算法同时给出支撑材料、检查日期、稳固情况与流转标记。

    三个动作与重算历史记录都调用它，因此同一株树读到的稳固情况必然一致。
    稳固情况、支撑状态两个对外字段保持原有字段名，值统一跟随支撑状态。
    """
    status = normalize_status(status)
    derived = {
        "status": status,
        MATERIAL_FIELD: resolve_material(entry),
        CHECK_DATE_FIELD: resolve_check_date(entry),
        "pending": is_pending(status),
        "abnormal": is_abnormal(status),
    }
    for field in STABILITY_FIELDS:
        derived[field] = status
    return derived


def apply_action(entry: dict[str, Any], action: str) -> tuple[str | None, str]:
    """校验动作并给出目标状态；不允许的动作返回可读原因，不改动记录。"""
    name = clean_text(action)
    target = ACTION_STATUS.get(name)
    if target is None:
        return None, f"动作「{name}」不属于树木支撑可执行范围"
    return target, f"支撑设施已{name}"


def recompute_row(entry: dict[str, Any]) -> dict[str, Any]:
    """按统一算法重算单条支撑记录，并用结果原地更新派生字段。"""
    status = normalize_status(entry.get("status"))
    entry.update(evaluate(entry, status))
    return entry


def recompute_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """统一算法变更后批量重算已有的支撑记录。"""
    for entry in rows:
        recompute_row(entry)
    return rows
