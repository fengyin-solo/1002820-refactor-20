"""树木支撑业务规则：状态流转、字段校验与筛选口径都收在这里。

稳固情况只有一份判定：支撑材料与检查日期只按一套算法推算，登记松动、
加固处理、拆除支撑三个动作统一改调 refresh_entry，同一株树在三个动作里
读到的稳固情况始终是同一个。已有支撑记录在服务启动时按统一算法重算。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.store import store

MODULE = "support"
REQUIRED_FIELDS = ["支撑编号", "所属树木", "支撑方式"]
LIST_FIELDS = ["支撑编号", "所属树木", "支撑方式", "支撑材料", "安装日期", "检查日期", "稳固情况", "支撑状态"]
STATUS_ORDER = ["稳固", "松动", "损坏", "已拆除"]
ACTION_RULES = {"登记松动": "松动", "加固处理": "稳固", "拆除支撑": "已拆除"}
REMOVED_STATUS = STATUS_ORDER[-1]
ABNORMAL_STATUSES = {"松动", "损坏"}

# 支撑材料的免检周期（天）：检查日期超出周期记松动，再超一倍记损坏
MATERIAL_DURABILITY = (("钢管", 365), ("镀锌", 365), ("金属", 365), ("木", 180), ("竹", 90))
DEFAULT_DURABILITY = 180
DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d")


def normalize_material(value: Any) -> str:
    """支撑材料只认一种写法：去掉全部空白，别的入口读到的才是同一份材料。"""
    return "".join(str(value or "").split())


def parse_inspection_date(value: Any) -> date | None:
    """检查日期只按一套算法解析，空缺或格式不认一律返回 None。"""
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def durability_days(material: str) -> int:
    for keyword, days in MATERIAL_DURABILITY:
        if keyword in material:
            return days
    return DEFAULT_DURABILITY


def assess_stability(material: Any, inspection_date: Any, *, today: date | None = None) -> str:
    """统一的稳固情况判定：只依赖支撑材料与检查日期，不看动作来源。"""
    inspected = parse_inspection_date(inspection_date)
    if inspected is None:
        return "松动"  # 没有有效检查日期的支撑按待复查的松动处理
    current = today or date.today()
    elapsed = max((current - inspected).days, 0)
    limit = durability_days(normalize_material(material))
    if elapsed <= limit:
        return "稳固"
    if elapsed <= limit * 2:
        return "松动"
    return "损坏"


def refresh_entry(entry: dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
    """共用判定入口：三个动作与存量重算都走这里，同一株树结果自然一致。"""
    material = normalize_material(entry.get("支撑材料"))
    inspected = parse_inspection_date(entry.get("检查日期"))
    entry["支撑材料"] = material
    entry["检查日期"] = inspected.isoformat() if inspected else ""
    status = str(entry.get("status") or STATUS_ORDER[0])
    if status not in STATUS_ORDER:
        status = STATUS_ORDER[0]
    entry["status"] = status
    entry["支撑状态"] = status
    if status == REMOVED_STATUS:
        entry["稳固情况"] = REMOVED_STATUS
    else:
        entry["稳固情况"] = assess_stability(material, inspected, today=today)
    entry["pending"] = status != REMOVED_STATUS
    entry["abnormal"] = status in ABNORMAL_STATUSES
    return entry


def recalculate_entries() -> None:
    """统一算法换过之后重算已有的支撑记录，养护看板随明细同步刷新。"""
    for row in store.rows(MODULE):
        refresh_entry(row)


class SupportService:
    def __init__(self) -> None:
        recalculate_entries()

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("支撑编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        tree = str(values.get("所属树木") or "").strip()
        for row in store.rows(MODULE):
            if row.get("status") != REMOVED_STATUS and str(row.get("所属树木") or "").strip() == tree:
                return None, f"所属树木「{tree}」已登记支撑设施，同一株树重复登记只认第一次"
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in LIST_FIELDS:
            entry[field] = values.get(field, "")
        entry["status"] = STATUS_ORDER[0]
        rows.append(refresh_entry(entry))
        return entry, ""

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"支撑设施 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于树木支撑可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        refresh_entry(entry)
        return entry, f"支撑设施已{action}"
