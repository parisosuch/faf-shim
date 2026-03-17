from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session, Shim, ShimCreate, ShimRule, ShimRuleCreate, RuleOperator

router = APIRouter(prefix="/shims", tags=["shims"])


@router.get("/operators")
def list_operators():
    return [{"value": op.value, "label": op.name} for op in RuleOperator]


@router.get("/", response_model=list[Shim])
def list_shims(session: Session = Depends(get_session)):
    return session.exec(select(Shim)).all()


@router.post("/", response_model=Shim, status_code=201)
def create_shim(body: ShimCreate, session: Session = Depends(get_session)):
    existing = session.exec(select(Shim).where(Shim.slug == body.slug)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Slug already in use")
    shim = Shim.model_validate(body)
    session.add(shim)
    session.commit()
    session.refresh(shim)
    return shim


@router.get("/{shim_id}", response_model=Shim)
def get_shim(shim_id: int, session: Session = Depends(get_session)):
    shim = session.get(Shim, shim_id)
    if not shim:
        raise HTTPException(status_code=404, detail="Shim not found")
    return shim


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


@router.delete("/{shim_id}/rules/{rule_id}", status_code=204)
def delete_rule(shim_id: int, rule_id: int, session: Session = Depends(get_session)):
    rule = session.get(ShimRule, rule_id)
    if not rule or rule.shim_id != shim_id:
        raise HTTPException(status_code=404, detail="Rule not found")
    session.delete(rule)
    session.commit()
