from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth import require_auth
from app.db import (
    get_session,
    Shim,
    ShimCreate,
    ShimRead,
    ShimUpdate,
    ShimRule,
    ShimRuleCreate,
    ShimRuleUpdate,
    RuleOperator,
    WebhookLog,
)
from app.forwarder import evaluate_rules

router = APIRouter(
    prefix="/shims", tags=["shims"], dependencies=[Depends(require_auth)]
)


@router.get("/operators")
def list_operators():
    return [{"value": op.value, "label": op.name} for op in RuleOperator]


@router.get("/", response_model=list[ShimRead])
def list_shims(session: Session = Depends(get_session)):
    shims = session.exec(select(Shim)).all()
    return [
        ShimRead(
            **shim.model_dump(),
            rules=session.exec(
                select(ShimRule)
                .where(ShimRule.shim_id == shim.id)
                .order_by(ShimRule.order)
            ).all(),
        )
        for shim in shims
    ]


@router.post("/", response_model=ShimRead, status_code=201)
def create_shim(body: ShimCreate, session: Session = Depends(get_session)):
    existing = session.exec(select(Shim).where(Shim.slug == body.slug)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Slug already in use")
    shim = Shim.model_validate(body)
    session.add(shim)
    session.commit()
    session.refresh(shim)
    return ShimRead(**shim.model_dump(), rules=[])


@router.get("/{shim_id}", response_model=ShimRead)
def get_shim(shim_id: int, session: Session = Depends(get_session)):
    shim = session.get(Shim, shim_id)
    if not shim:
        raise HTTPException(status_code=404, detail="Shim not found")
    rules = session.exec(
        select(ShimRule).where(ShimRule.shim_id == shim_id).order_by(ShimRule.order)
    ).all()
    return ShimRead(**shim.model_dump(), rules=rules)


class TestPayloadRequest(BaseModel):
    payload: dict[str, Any]


class TestPayloadResponse(BaseModel):
    matched_rule: ShimRule | None
    target_url: str


@router.post("/{shim_id}/test", response_model=TestPayloadResponse)
def test_shim(
    shim_id: int, body: TestPayloadRequest, session: Session = Depends(get_session)
):
    shim = session.get(Shim, shim_id)
    if not shim:
        raise HTTPException(status_code=404, detail="Shim not found")
    rules = session.exec(
        select(ShimRule).where(ShimRule.shim_id == shim_id).order_by(ShimRule.order)
    ).all()
    matched_url = evaluate_rules(rules, body.payload)
    matched_rule = (
        next((r for r in rules if r.target_url == matched_url), None)
        if matched_url
        else None
    )
    return TestPayloadResponse(
        matched_rule=matched_rule,
        target_url=matched_url or shim.target_url,
    )


@router.patch("/{shim_id}", response_model=ShimRead)
def update_shim(
    shim_id: int, body: ShimUpdate, session: Session = Depends(get_session)
):
    shim = session.get(Shim, shim_id)
    if not shim:
        raise HTTPException(status_code=404, detail="Shim not found")
    if body.slug and body.slug != shim.slug:
        existing = session.exec(select(Shim).where(Shim.slug == body.slug)).first()
        if existing:
            raise HTTPException(status_code=409, detail="Slug already in use")
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(shim, field, val)
    session.add(shim)
    session.commit()
    session.refresh(shim)
    rules = session.exec(
        select(ShimRule).where(ShimRule.shim_id == shim_id).order_by(ShimRule.order)
    ).all()
    return ShimRead(**shim.model_dump(), rules=rules)


@router.delete("/{shim_id}", status_code=204)
def delete_shim(shim_id: int, session: Session = Depends(get_session)):
    shim = session.get(Shim, shim_id)
    if not shim:
        raise HTTPException(status_code=404, detail="Shim not found")
    # cascade delete rules manually (SQLite doesn't enforce FK cascades by default)
    rules = session.exec(select(ShimRule).where(ShimRule.shim_id == shim_id)).all()
    for rule in rules:
        session.delete(rule)
    session.delete(shim)
    session.commit()


@router.get("/{shim_id}/rules", response_model=list[ShimRule])
def list_rules(shim_id: int, session: Session = Depends(get_session)):
    if not session.get(Shim, shim_id):
        raise HTTPException(status_code=404, detail="Shim not found")
    return session.exec(
        select(ShimRule).where(ShimRule.shim_id == shim_id).order_by(ShimRule.order)
    ).all()


@router.post("/{shim_id}/rules", response_model=ShimRule, status_code=201)
def create_rule(
    shim_id: int, body: ShimRuleCreate, session: Session = Depends(get_session)
):
    if not session.get(Shim, shim_id):
        raise HTTPException(status_code=404, detail="Shim not found")
    rule = ShimRule.model_validate(body, update={"shim_id": shim_id})
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


@router.patch("/{shim_id}/rules/{rule_id}", response_model=ShimRule)
def update_rule(
    shim_id: int,
    rule_id: int,
    body: ShimRuleUpdate,
    session: Session = Depends(get_session),
):
    rule = session.get(ShimRule, rule_id)
    if not rule or rule.shim_id != shim_id:
        raise HTTPException(status_code=404, detail="Rule not found")
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(rule, field, val)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


@router.delete("/{shim_id}/rules/{rule_id}", status_code=204)
def delete_rule(shim_id: int, rule_id: int, session: Session = Depends(get_session)):
    rule = session.get(ShimRule, rule_id)
    if not rule or rule.shim_id != shim_id:
        raise HTTPException(status_code=404, detail="Rule not found")
    session.delete(rule)
    session.commit()


@router.get("/{shim_id}/logs", response_model=list[WebhookLog])
def list_logs(
    shim_id: int,
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
):
    if not session.get(Shim, shim_id):
        raise HTTPException(status_code=404, detail="Shim not found")
    return session.exec(
        select(WebhookLog)
        .where(WebhookLog.shim_id == shim_id)
        .order_by(WebhookLog.received_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()


@router.get("/{shim_id}/logs/{log_id}", response_model=WebhookLog)
def get_log(shim_id: int, log_id: int, session: Session = Depends(get_session)):
    log = session.get(WebhookLog, log_id)
    if not log or log.shim_id != shim_id:
        raise HTTPException(status_code=404, detail="Log not found")
    return log
