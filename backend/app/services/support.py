"""树木支撑业务规则：状态流转、字段校验与筛选口径都收在这里。

三个动作（登记松动、加固处理、拆除支撑）不再各写一遍判定，统一调用
``support_rules`` 里的共用实现；支撑材料、检查日期、稳固情况也只按那一套算法算。
"""
from __future__ import annotations

from typing import Any

from app.services import support_rules as rules
from app.store import store

MODULE = "support"
REQUIRED_FIELDS = ["支撑编号", "所属树木", "支撑方式"]
# 登记时允许一起提交的来源字段；支撑材料、检查日期等派生字段由共用判定算出。
OPTIONAL_FIELDS = ["支撑材料", "安装日期", "检查日期"]


class SupportService:
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

    def find_tree_entry(self, tree_name: str) -> dict[str, Any] | None:
        """按所属树木读取第一份有效支撑记录：同一株树重复登记只认第一次。"""
        target = rules.clean_text(tree_name)
        if not target:
            return None
        for row in store.rows(MODULE):
            if rules.clean_text(row.get("所属树木")) == target:
                return row
        return None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        missing = [field for field in REQUIRED_FIELDS if not rules.clean_text(values.get(field))]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"

        tree_name = rules.clean_text(values.get("所属树木"))
        if self.find_tree_entry(tree_name) is not None:
            return None, f"所属树木「{tree_name}」已登记过支撑，重复登记只认第一次"

        rows = store.rows(MODULE)
        entry: dict[str, Any] = {
            "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1
        }
        for field in REQUIRED_FIELDS:
            entry[field] = rules.clean_text(values.get(field))
        for field in OPTIONAL_FIELDS:
            text = rules.clean_text(values.get(field))
            if text:
                entry[field] = text

        # 初始支撑状态与派生字段统一走共用判定，避免与动作判定各算各的。
        entry.update(rules.evaluate(entry, rules.DEFAULT_STATUS))
        rows.append(entry)
        return entry, ""

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"支撑设施 {entry_id} 不存在或已归档"
        target, message = rules.apply_action(entry, action)
        if target is None:
            return None, message
        # 三个动作统一改调这份判定：状态一改，材料、检查日期、稳固情况一起重算。
        entry.update(rules.evaluate(entry, target))
        return entry, message

    def tree_material(self, tree_name: str) -> dict[str, Any] | None:
        """供其它入口（乔木管理）读取某株树的支撑材料，口径与本模块对齐。"""
        entry = self.find_tree_entry(tree_name)
        if entry is None:
            return None
        return {
            "所属树木": rules.clean_text(entry.get("所属树木")),
            "支撑编号": entry.get("支撑编号"),
            "支撑材料": rules.resolve_material(entry),
            "检查日期": rules.resolve_check_date(entry),
        }
