CREATE_USERS_SQL = """
create table if not exists public.users (
  user_id integer primary key,
  name text not null,
  timezone text not null,
  languages jsonb not null,
  domain_tags jsonb not null,
  availability_local jsonb not null,
  avg_interview_time_min integer not null,
  avg_interview_cost_usd numeric(10,2) not null,
  avg_csat numeric(3,2) not null,
  completion_rate numeric(4,2) not null,
  past_interview_count integer not null
);
"""

CREATE_INTERVIEWERS_SQL = """
create table if not exists public.interviewers (
  interviewer_id integer primary key,
  name text not null,
  timezone text not null,
  languages jsonb not null,
  expertise_tags jsonb not null,
  rate_usd numeric(10,2) not null,
  avg_time_min integer not null,
  empathy_score numeric(3,2) not null,
  reliability numeric(3,2) not null,
  max_concurrent integer,
  availability_local jsonb not null
);
"""

CREATE_ASSIGNMENTS_SQL = """
create table if not exists public.assignments (
  id              bigserial primary key,
  created_at      timestamptz not null default now(),
  user_id         integer not null,
  interviewer_id  integer null,
  topics          jsonb not null,
  language        text not null,
  budget          numeric(10,2) not null,
  sla_min         integer not null,
  sensitivity     boolean not null,
  score           numeric(10,4) null,
  status          text not null
);
"""
