from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
import sqlalchemy as sa

from .models import Query, CompleteBody, AssignmentOut
from .cache import get_q
from .db import load_entities, log_assignment_to_db
from .scoring import score_interviewer

router = APIRouter()

@router.get("/healthz")
def healthz(request: Request):
    try:
        request.app.state.redis.ping()
        with request.app.state.engine.connect() as conn:
            conn.execute(sa.text("select 1"))
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@router.post("/v1/admin/reload")
def admin_reload(request: Request):
    users, interviewers = load_entities(request.app.state.engine)
    request.app.state.users = users
    request.app.state.interviewers = interviewers
    for itv in interviewers:
        request.app.state.redis.setnx(f"interviewer:{itv['interviewer_id']}:queue", 0)
    return {"status": "ok", "users": len(users), "interviewers": len(interviewers)}

@router.post("/v1/admin/reset_queues")
def admin_reset_queues(request: Request):
    for itv in request.app.state.interviewers:
        request.app.state.redis.set(f"interviewer:{itv['interviewer_id']}:queue", 0)
    return {"status": "ok", "reset": len(request.app.state.interviewers)}

@router.get("/v1/state")
def state(request: Request):
    rows = []
    for itv in request.app.state.interviewers:
        rows.append({
            "interviewer_id": itv["interviewer_id"],
            "languages": itv["languages"],
            "expertise_tags": itv["expertise_tags"],
            "rate_usd": itv["rate_usd"],
            "avg_time_min": itv["avg_time_min"],
            "current_queue": get_q(request.app.state.redis, itv["interviewer_id"]),
            "reliability": itv["reliability"],
            "empathy_score": itv["empathy_score"],
            "max_concurrent": itv.get("max_concurrent", None),
        })
    return {"interviewers": rows}

@router.get("/v1/state/{interviewer_id}")
def state_one(interviewer_id: int, request: Request):
    itv = next((i for i in request.app.state.interviewers if i["interviewer_id"] == interviewer_id), None)
    if not itv:
        raise HTTPException(status_code=404, detail="interviewer_not_found")
    return {
        "interviewer_id": itv["interviewer_id"],
        "current_queue": get_q(request.app.state.redis, itv["interviewer_id"]),
        "max_concurrent": itv.get("max_concurrent", None),
    }

@router.post("/v1/complete")
def complete(body: CompleteBody, request: Request):
    key = f"interviewer:{body.interviewer_id}:queue"
    new_q = int(request.app.state.decr_lua(keys=[key]))
    return {"status": "ok", "interviewer_id": body.interviewer_id, "current_queue": new_q}

@router.post("/v1/route", response_model=AssignmentOut)
def route(query: Query, request: Request):
    # Resolve user
    if query.user_id is not None:
        user = next((u for u in request.app.state.users if u["user_id"] == query.user_id), None)
        if user is None:
            return AssignmentOut(status="no_match", reason="user_not_found")
    else:
        if not request.app.state.users:
            return AssignmentOut(status="no_match", reason="no_users_loaded")
        import random
        user = random.choice(request.app.state.users)

    # Score candidates
    scored = []
    for itv in request.app.state.interviewers:
        s = score_interviewer(user, query, itv, request.app.state.redis)
        if s == float("-inf"):
            continue
        scored.append((s, itv))

    if not scored:
        payload = {
            "user_id": user["user_id"],
            "interviewer_id": None,
            "topics": query.topics,
            "language": query.language,
            "budget": query.budget,
            "sla_min": query.sla_min,
            "sensitivity": query.sensitivity,
            "score": None,
            "status": "no_match",
        }
        try:
            log_assignment_to_db(request.app.state.engine, payload)
        except Exception:
            pass
        return AssignmentOut(status="no_match", reason="no_candidates")

    scored.sort(key=lambda x: x[0], reverse=True)

    # capacity-guarded commit
    for s, itv in scored:
        key = f"interviewer:{itv['interviewer_id']}:queue"
        new_q = request.app.state.redis.incr(key)
        try:
            max_concurrent = int(itv.get("max_concurrent", 999_999))
            if new_q > max_concurrent:
                request.app.state.redis.decr(key)
                continue

            assignment = {
                "user_id": user["user_id"],
                "interviewer_id": itv["interviewer_id"],
                "topics": query.topics,
                "language": query.language,
                "budget": query.budget,
                "sla_min": query.sla_min,
                "sensitivity": query.sensitivity,
                "score": round(float(s), 3),
                "status": "assigned",
            }
            try:
                log_assignment_to_db(request.app.state.engine, assignment)
            except Exception:
                pass

            return AssignmentOut(
                status="assigned",
                user_id=user["user_id"],
                interviewer_id=itv["interviewer_id"],
                score=assignment["score"],
                current_queue=int(new_q),
            )
        except Exception:
            request.app.state.redis.decr(key)
            continue

    # all at capacity
    payload = {
        "user_id": user["user_id"],
        "interviewer_id": None,
        "topics": query.topics,
        "language": query.language,
        "budget": query.budget,
        "sla_min": query.sla_min,
        "sensitivity": query.sensitivity,
        "score": None,
        "status": "no_match",
    }
    try:
        log_assignment_to_db(request.app.state.engine, payload)
    except Exception:
        pass
    return AssignmentOut(status="no_match", reason="all_candidates_at_capacity")
