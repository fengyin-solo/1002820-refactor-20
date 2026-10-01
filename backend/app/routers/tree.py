"""乔木管理接口：维护乔木，覆盖记录衰弱、复壮作业、登记枯死等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.tree import TreeService

router = APIRouter(prefix="/api/tree", tags=["乔木管理"])

service = TreeService()

LIST_FIELDS = ["树木编号", "树种名称", "胸径", "冠幅", "树龄", "定植日期", "管护人员", "树木状态"]
STATUSES = ["生长正常", "长势衰弱", "濒危", "已枯死"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按树木编号检索"),
    status: str | None = Query(default=None, description="生长正常、长势衰弱、濒危、已枯死"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按树木编号与状态过滤乔木管理列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条乔木明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"乔木 {entry_id} 不存在或已归档")
    return entry


@router.get("/support-material/{tree_name}", response_model=dict)
def get_support_material(tree_name: str) -> dict:
    """另一入口读取某株树的支撑材料，口径与树木支撑模块保持一致。"""
    material = service.support_material(tree_name)
    if material is None:
        raise HTTPException(status_code=404, detail=f"所属树木「{tree_name}」暂无支撑记录")
    return material


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条乔木，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="乔木已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条乔木执行记录衰弱、复壮作业、登记枯死；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出乔木管理清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "tree", "total": total, "items": items}
