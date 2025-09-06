from __future__ import annotations

import json
import time
from decimal import Decimal
from typing import Any, Dict, List, Tuple

import sqlalchemy as sa
from sqlalchemy.engine import Engine

from .schema_sql import (
    CREATE_USERS_SQL,
    CREATE_INTERVIEWERS_SQL,
    CREATE_ASSIGNMENTS_SQL,
)

def _to_py(v: Any) -> Any:
    return float(v) if isinstance(v, Decimal) else v

def _normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    row = dict(row)
    for k in ("languages", "domain_tags", "availability_local", "expertise_tags", "topics"):
        if k in row and isinstance(row[k], str):
            try:
                row[k] = json.loads(row[k])
            except Exception:
                pass
    for k, v in list(row.items()):
        row[k] = _to_py(v)
    return row

def wait_for_postgres(url: str, attempts: int = 10, base_sleep: float = 0.3) -> Engine:
    eng = sa.create_engine(url, future=True, pool_pre_ping=True, pool_recycle=1800)
    for i in range(attempts):
        try:
            with eng.connect() as conn:
                conn.execute(sa.text("select 1"))
            return eng
        except Exception:
            time.sleep(base_sleep * (2**i))
    raise RuntimeError(f"Postgres not reachable at {url}")

def ensure_schema_and_seed(engine: Engine, users_path: str, interviewers_path: str, logger) -> None:
    with engine.begin() as conn:
        conn.execute(sa.text(CREATE_USERS_SQL))
        conn.execute(sa.text(CREATE_INTERVIEWERS_SQL))
        conn.execute(sa.text(CREATE_ASSIGNMENTS_SQL))

        users_count = conn.execute(sa.text("select count(*) from users")).scalar_one()
        inter_count = conn.execute(sa.text("select count(*) from interviewers")).scalar_one()

        if users_count == 0:
            logger.info("Seeding users from %s", users_path)
            users = json.load(open(users_path))
            for u in users:
                conn.execute(
                    sa.text("""
                        insert into users values (
                          :user_id,:name,:timezone,
                          cast(:languages as jsonb),
                          cast(:domain_tags as jsonb),
                          cast(:availability_local as jsonb),
                          :avg_interview_time_min,:avg_interview_cost_usd,
                          :avg_csat,:completion_rate,:past_interview_count
                        )
                    """),
                    {
                        **u,
                        "languages": json.dumps(u["languages"]),
                        "domain_tags": json.dumps(u["domain_tags"]),
                        "availability_local": json.dumps(u["availability_local"]),
                    },
                )

        if inter_count == 0:
            logger.info("Seeding interviewers from %s", interviewers_path)
            inters = json.load(open(interviewers_path))
            for i in inters:
                i = {k: v for k, v in i.items() if k != "current_queue"}  # queues live in Redis
                conn.execute(
                    sa.text("""
                        insert into interviewers values (
                          :interviewer_id,:name,:timezone,
                          cast(:languages as jsonb),
                          cast(:expertise_tags as jsonb),
                          :rate_usd,:avg_time_min,:empathy_score,:reliability,
                          :max_concurrent,cast(:availability_local as jsonb)
                        )
                    """),
                    {
                        **i,
                        "languages": json.dumps(i["languages"]),
                        "expertise_tags": json.dumps(i["expertise_tags"]),
                        "availability_local": json.dumps(i["availability_local"]),
                    },
                )

def load_entities(engine: Engine) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    with engine.connect() as conn:
        users = conn.execute(sa.text("select * from users")).mappings().all()
        inters = conn.execute(sa.text("select * from interviewers")).mappings().all()
    return ([_normalize_row(u) for u in users], [_normalize_row(i) for i in inters])

def log_assignment_to_db(engine: Engine, payload: Dict[str, Any]) -> None:
    stmt = sa.text("""
        insert into assignments
            (user_id, interviewer_id, topics, language, budget, sla_min, sensitivity, score, status)
        values
            (:user_id, :interviewer_id, cast(:topics as jsonb), :language, :budget, :sla_min, :sensitivity, :score, :status)
    """)
    params = {
        "user_id": payload.get("user_id"),
        "interviewer_id": payload.get("interviewer_id"),
        "topics": json.dumps(payload.get("topics", [])),
        "language": payload.get("language"),
        "budget": payload.get("budget"),
        "sla_min": payload.get("sla_min"),
        "sensitivity": payload.get("sensitivity"),
        "score": payload.get("score"),
        "status": payload.get("status", "assigned"),
    }
    with engine.begin() as conn:
        conn.execute(stmt, params)
