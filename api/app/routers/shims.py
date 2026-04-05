from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import app_config as _app_config
from app import cache
from app.auth import require_auth
from app.db import (
    get_session,
    Shim,
    ShimCreate,
    ShimRead,
    ShimUpdate,
    ShimExport,
    ShimRule,
    ShimRuleBase,
    ShimRuleCreate,
    ShimRuleUpdate,
    ShimVariable,
    ShimVariableCreate,
    ShimVariableUpdate,
    RuleOperator,
    WebhookLog,
)
from app.forwarder import find_matching_rule, render_headers, render_template
from app.utils import now

router = APIRouter(
    prefix="/shims", tags=["shims"], dependencies=[Depends(require_auth)]
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_shim_read(shim_id: int, session: AsyncSession) -> ShimRead:
    """Fetch a Shim with its rules and variables and return as ShimRead."""
    shim = await session.get(Shim, shim_id)
    if not shim:
        raise HTTPException(status_code=404, detail="Shim not found")
    rules = (
        await session.exec(
            select(ShimRule).where(ShimRule.shim_id == shim_id).order_by(ShimRule.order)
        )
    ).all()
    variables = (
        await session.exec(select(ShimVariable).where(ShimVariable.shim_id == shim_id))
    ).all()
    return ShimRead(**shim.model_dump(), rules=rules, variables=variables)


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------


@router.get("/operators")
def list_operators():
    return [{"value": op.value, "label": op.name} for op in RuleOperator]


# ---------------------------------------------------------------------------
# Shim CRUD
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[ShimRead])
async def list_shims(session: AsyncSession = Depends(get_session)):
    shims = (await session.exec(select(Shim))).all()
    result = []
    for shim in shims:
        rules = (
            await session.exec(
                select(ShimRule)
                .where(ShimRule.shim_id == shim.id)
                .order_by(ShimRule.order)
            )
        ).all()
        variables = (
            await session.exec(
                select(ShimVariable).where(ShimVariable.shim_id == shim.id)
            )
        ).all()
        result.append(ShimRead(**shim.model_dump(), rules=rules, variables=variables))
    return result


@router.post("/", response_model=ShimRead, status_code=201)
async def create_shim(body: ShimCreate, session: AsyncSession = Depends(get_session)):
    existing = (await session.exec(select(Shim).where(Shim.slug == body.slug))).first()
    if existing:
        raise HTTPException(status_code=409, detail="Slug already in use")
    shim = Shim.model_validate(body)
    session.add(shim)
    await session.commit()
    await session.refresh(shim)
    return ShimRead(**shim.model_dump(), rules=[], variables=[])


@router.post("/import", response_model=ShimRead, status_code=201)
async def import_shim(body: ShimExport, session: AsyncSession = Depends(get_session)):
    existing = (await session.exec(select(Shim).where(Shim.slug == body.slug))).first()
    if existing:
        raise HTTPException(status_code=409, detail="Slug already in use")
    shim = Shim.model_validate(body)
    session.add(shim)
    await session.flush()
    for rule_data in body.rules:
        rule = ShimRule.model_validate(rule_data, update={"shim_id": shim.id})
        session.add(rule)
    for var_data in body.variables:
        session.add(
            ShimVariable(shim_id=shim.id, key=var_data.key, value=var_data.value)
        )
    await session.commit()
    await session.refresh(shim)
    return await _get_shim_read(shim.id, session)


@router.get("/{shim_id}/export", response_model=ShimExport)
async def export_shim(shim_id: int, session: AsyncSession = Depends(get_session)):
    shim = await session.get(Shim, shim_id)
    if not shim:
        raise HTTPException(status_code=404, detail="Shim not found")
    rules = (
        await session.exec(
            select(ShimRule).where(ShimRule.shim_id == shim_id).order_by(ShimRule.order)
        )
    ).all()
    variables = (
        await session.exec(select(ShimVariable).where(ShimVariable.shim_id == shim_id))
    ).all()
    return ShimExport(
        **shim.model_dump(exclude={"id", "created_at"}),
        rules=[ShimRuleBase(**r.model_dump(exclude={"id", "shim_id"})) for r in rules],
        variables=[ShimVariableCreate(key=v.key, value=v.value) for v in variables],
    )


@router.get("/{shim_id}", response_model=ShimRead)
async def get_shim(shim_id: int, session: AsyncSession = Depends(get_session)):
    return await _get_shim_read(shim_id, session)


@router.patch("/{shim_id}", response_model=ShimRead)
async def update_shim(
    shim_id: int, body: ShimUpdate, session: AsyncSession = Depends(get_session)
):
    shim = await session.get(Shim, shim_id)
    if not shim:
        raise HTTPException(status_code=404, detail="Shim not found")
    if body.slug and body.slug != shim.slug:
        existing = (
            await session.exec(select(Shim).where(Shim.slug == body.slug))
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Slug already in use")
    old_slug = shim.slug
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(shim, field, val)
    session.add(shim)
    await session.commit()
    await session.refresh(shim)
    cache.invalidate(old_slug)
    if shim.slug != old_slug:
        cache.invalidate(shim.slug)
    return await _get_shim_read(shim_id, session)


@router.delete("/{shim_id}", status_code=204)
async def delete_shim(shim_id: int, session: AsyncSession = Depends(get_session)):
    shim = await session.get(Shim, shim_id)
    if not shim:
        raise HTTPException(status_code=404, detail="Shim not found")
    cache.invalidate(shim.slug)
    for rule in (
        await session.exec(select(ShimRule).where(ShimRule.shim_id == shim_id))
    ).all():
        await session.delete(rule)
    for var in (
        await session.exec(select(ShimVariable).where(ShimVariable.shim_id == shim_id))
    ).all():
        await session.delete(var)
    await session.delete(shim)
    await session.commit()


# ---------------------------------------------------------------------------
# Rule CRUD
# ---------------------------------------------------------------------------


@router.get("/{shim_id}/rules", response_model=list[ShimRule])
async def list_rules(shim_id: int, session: AsyncSession = Depends(get_session)):
    if not await session.get(Shim, shim_id):
        raise HTTPException(status_code=404, detail="Shim not found")
    return (
        await session.exec(
            select(ShimRule).where(ShimRule.shim_id == shim_id).order_by(ShimRule.order)
        )
    ).all()


@router.post("/{shim_id}/rules", response_model=ShimRule, status_code=201)
async def create_rule(
    shim_id: int, body: ShimRuleCreate, session: AsyncSession = Depends(get_session)
):
    shim = await session.get(Shim, shim_id)
    if not shim:
        raise HTTPException(status_code=404, detail="Shim not found")
    cache.invalidate(shim.slug)
    rule = ShimRule.model_validate(body, update={"shim_id": shim_id})
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return rule


@router.patch("/{shim_id}/rules/{rule_id}", response_model=ShimRule)
async def update_rule(
    shim_id: int,
    rule_id: int,
    body: ShimRuleUpdate,
    session: AsyncSession = Depends(get_session),
):
    rule = await session.get(ShimRule, rule_id)
    if not rule or rule.shim_id != shim_id:
        raise HTTPException(status_code=404, detail="Rule not found")
    shim = await session.get(Shim, shim_id)
    if shim:
        cache.invalidate(shim.slug)
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(rule, field, val)
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return rule


@router.delete("/{shim_id}/rules/{rule_id}", status_code=204)
async def delete_rule(
    shim_id: int, rule_id: int, session: AsyncSession = Depends(get_session)
):
    rule = await session.get(ShimRule, rule_id)
    if not rule or rule.shim_id != shim_id:
        raise HTTPException(status_code=404, detail="Rule not found")
    shim = await session.get(Shim, shim_id)
    if shim:
        cache.invalidate(shim.slug)
    await session.delete(rule)
    await session.commit()


# ---------------------------------------------------------------------------
# Variable CRUD
# ---------------------------------------------------------------------------


@router.get("/{shim_id}/variables", response_model=list[ShimVariable])
async def list_variables(shim_id: int, session: AsyncSession = Depends(get_session)):
    if not await session.get(Shim, shim_id):
        raise HTTPException(status_code=404, detail="Shim not found")
    return (
        await session.exec(select(ShimVariable).where(ShimVariable.shim_id == shim_id))
    ).all()


@router.post("/{shim_id}/variables", response_model=ShimVariable, status_code=201)
async def create_variable(
    shim_id: int,
    body: ShimVariableCreate,
    session: AsyncSession = Depends(get_session),
):
    shim = await session.get(Shim, shim_id)
    if not shim:
        raise HTTPException(status_code=404, detail="Shim not found")
    var = ShimVariable(shim_id=shim_id, key=body.key, value=body.value)
    session.add(var)
    await session.commit()
    await session.refresh(var)
    cache.invalidate(shim.slug)
    return var


@router.patch("/{shim_id}/variables/{var_id}", response_model=ShimVariable)
async def update_variable(
    shim_id: int,
    var_id: int,
    body: ShimVariableUpdate,
    session: AsyncSession = Depends(get_session),
):
    var = await session.get(ShimVariable, var_id)
    if not var or var.shim_id != shim_id:
        raise HTTPException(status_code=404, detail="Variable not found")
    shim = await session.get(Shim, shim_id)
    if shim:
        cache.invalidate(shim.slug)
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(var, field, val)
    session.add(var)
    await session.commit()
    await session.refresh(var)
    return var


@router.delete("/{shim_id}/variables/{var_id}", status_code=204)
async def delete_variable(
    shim_id: int, var_id: int, session: AsyncSession = Depends(get_session)
):
    var = await session.get(ShimVariable, var_id)
    if not var or var.shim_id != shim_id:
        raise HTTPException(status_code=404, detail="Variable not found")
    shim = await session.get(Shim, shim_id)
    if shim:
        cache.invalidate(shim.slug)
    await session.delete(var)
    await session.commit()


# ---------------------------------------------------------------------------
# Template render (live preview while editing)
# ---------------------------------------------------------------------------


class RenderTemplateRequest(BaseModel):
    template: str
    payload: dict[str, Any] = {}


class RenderTemplateResponse(BaseModel):
    result: str | None = None
    error: str | None = None


@router.post("/{shim_id}/render-template", response_model=RenderTemplateResponse)
async def render_shim_template(
    shim_id: int,
    body: RenderTemplateRequest,
    session: AsyncSession = Depends(get_session),
):
    shim = await session.get(Shim, shim_id)
    if not shim:
        raise HTTPException(status_code=404, detail="Shim not found")
    variables = (
        await session.exec(select(ShimVariable).where(ShimVariable.shim_id == shim_id))
    ).all()
    vars_dict = {v.key: v.value for v in variables}
    try:
        result = render_template(body.template, body.payload, vars_dict).decode()
        return RenderTemplateResponse(result=result)
    except ValueError as e:
        return RenderTemplateResponse(error=str(e))


# ---------------------------------------------------------------------------
# Test dry-run
# ---------------------------------------------------------------------------


class TestPayloadRequest(BaseModel):
    payload: dict[str, Any]


class TestPayloadResponse(BaseModel):
    matched_rule: ShimRule | None
    target_url: str
    rendered_body: str | None = None
    rendered_headers: dict | None = None


@router.post("/{shim_id}/test", response_model=TestPayloadResponse)
async def test_shim(
    shim_id: int, body: TestPayloadRequest, session: AsyncSession = Depends(get_session)
):
    shim = await session.get(Shim, shim_id)
    if not shim:
        raise HTTPException(status_code=404, detail="Shim not found")
    rules = (
        await session.exec(
            select(ShimRule).where(ShimRule.shim_id == shim_id).order_by(ShimRule.order)
        )
    ).all()
    variables = (
        await session.exec(select(ShimVariable).where(ShimVariable.shim_id == shim_id))
    ).all()

    matched_rule = find_matching_rule(rules, body.payload)
    target_url = (matched_rule.target_url if matched_rule else None) or shim.target_url
    active_template = (
        matched_rule.body_template if matched_rule else None
    ) or shim.body_template

    vars_dict = {v.key: v.value for v in variables}

    rendered_body: str | None = None
    if active_template:
        try:
            rendered_body = render_template(
                active_template, body.payload, vars_dict
            ).decode()
        except ValueError as e:
            rendered_body = f"Template error: {e}"

    rendered_headers: dict | None = None
    if shim.headers and shim.headers != "{}":
        try:
            rendered_headers = render_headers(shim.headers, body.payload, vars_dict)
        except Exception:
            rendered_headers = None

    return TestPayloadResponse(
        matched_rule=matched_rule,
        target_url=target_url,
        rendered_body=rendered_body,
        rendered_headers=rendered_headers,
    )


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------


@router.get("/{shim_id}/logs", response_model=list[WebhookLog])
async def list_logs(
    shim_id: int,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    shim = await session.get(Shim, shim_id)
    if not shim:
        raise HTTPException(status_code=404, detail="Shim not found")

    cfg = _app_config.get()
    retention_days = (
        shim.log_retention_days
        if shim.log_retention_days is not None
        else cfg.log_retention_days
    )

    query = select(WebhookLog).where(WebhookLog.shim_id == shim_id)
    if retention_days > 0:
        cutoff = now() - timedelta(days=retention_days)
        query = query.where(WebhookLog.received_at >= cutoff)

    return (
        await session.exec(
            query.order_by(WebhookLog.received_at.desc()).offset(offset).limit(limit)
        )
    ).all()


@router.get("/{shim_id}/logs/{log_id}", response_model=WebhookLog)
async def get_log(
    shim_id: int, log_id: int, session: AsyncSession = Depends(get_session)
):
    log = await session.get(WebhookLog, log_id)
    if not log or log.shim_id != shim_id:
        raise HTTPException(status_code=404, detail="Log not found")
    return log
