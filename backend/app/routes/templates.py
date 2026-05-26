"""V10 §9.1 — Hot template endpoints.

Routes:
    GET  /templates                  list all templates
    GET  /templates/{tid}            fetch one
    POST /templates/{tid}/apply      apply to a payload (preview only)
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.flow.templates import apply_template, get_registry

from ..security import get_current_user
from ..db import User


router = APIRouter(prefix="/templates", tags=["templates"])


class TemplateApplyIn(BaseModel):
    payload: dict[str, Any] = {}
    lead_name: str = "主角"


@router.get("")
def list_templates(_user: User = Depends(get_current_user)):
    reg = get_registry()
    return {"templates": [t.to_dict() for t in reg.list_templates()]}


@router.get("/{tid}")
def get_template(tid: str, _user: User = Depends(get_current_user)):
    reg = get_registry()
    tpl = reg.get(tid)
    if tpl is None:
        raise HTTPException(status_code=404, detail=f"template '{tid}' not found")
    return tpl.to_dict()


@router.post("/{tid}/apply")
def apply_template_endpoint(
    tid: str, body: TemplateApplyIn,
    _user: User = Depends(get_current_user),
):
    reg = get_registry()
    tpl = reg.get(tid)
    if tpl is None:
        raise HTTPException(status_code=404, detail=f"template '{tid}' not found")
    merged = apply_template(tpl, body.payload, lead_name=body.lead_name)
    return {"template_id": tid, "applied_payload": merged}
