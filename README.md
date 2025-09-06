# Terac Routing Demo

A small, production-minded demo that **routes incoming customer queries to interviewers in real time**. It showcases:

- **Synthetic data generation** for users, interviewers, and transcripts  
- **Live routing** with scoring, capacity guards, and queues  

The goal is to make design choices explicit, easy to test, and easy to scale.

---

## Run (Postgres + Redis)

```bash
pip install -r requirements.txt

export SUPABASE_DB_URL='postgresql://.../postgres?sslmode=require'
export REDIS_URL='redis://localhost:6379/0'

uvicorn app.app:app --host 0.0.0.0 --port 8000 --reload
```

---

## Endpoints

- `POST /v1/route` — route a query  
- `POST /v1/complete` — decrement queue  
- `GET  /v1/state` — interviewer queues & attrs  
- `POST /v1/admin/reload` — reload from DB  
- `POST /v1/admin/reset_queues` — zero queues  
- `GET  /healthz` — health check

## Tests & Commands

### 1) Health + State

```bash
# Verify env vars (from project root)
grep -E 'SUPABASE_DB_URL|REDIS_URL' .env

# Redis up? (Docker)
docker ps | grep redis
docker exec -it terac-redis redis-cli ping   # expect: PONG

# Liveness / dependencies
curl -s http://localhost:8000/healthz | python -m json.tool

# All interviewers + current queues
curl -s http://localhost:8000/v1/state | python -m json.tool
```

### 2) Happy Path Route (English, budget fits, known user)

```bash
curl -s -X POST http://localhost:8000/v1/route \
  -H 'content-type: application/json' \
  -d '{
        "topics": ["FinTech", "Chargebacks"],
        "language": "English",
        "budget": 75.0,
        "sensitivity": false,
        "sla_min": 30,
        "user_id": 42
      }' | python -m json.tool

# expected response shape:
{
  "status": "assigned",
  "user_id": 42,
  "interviewer_id": 7,
  "score": 1.87,
  "current_queue": 1
}
```

### 3) Inspect Interviewer Queues

``` bash
# Global view
curl -s http://localhost:8000/v1/state | python -m json.tool

# Single interviewer (replace 7 with the ID from your route response)
curl -s http://localhost:8000/v1/state/7 | python -m json.tool
```

### 4) Mark Completion (decrement a queue)

```bash
# Replace 7 with the interviewer_id you saw earlier
curl -s -X POST http://localhost:8000/v1/complete \
  -H 'content-type: application/json' \
  -d '{"interviewer_id": 7}' | python -m json.tool
```

### 5) Admin Helpers

```bash
# Reload users/interviewers from Postgres
curl -s -X POST http://localhost:8000/v1/admin/reload | python -m json.tool

# Zero out all queues
curl -s -X POST http://localhost:8000/v1/admin/reset_queues | python -m json.tool
```

### 6) Edge Cases (Validation)

```bash
# Unknown user -> user_not_found
curl -s -X POST http://localhost:8000/v1/route \
  -H 'content-type: application/json' \
  -d '{
        "topics": ["FinTech"],
        "language": "English",
        "budget": 50,
        "sensitivity": false,
        "sla_min": 20,
        "user_id": 99999
      }' | python -m json.tool
```

```bash
# Unsupported languages -> no_candidates
curl -s -X POST http://localhost:8000/v1/route \
  -H 'content-type: application/json' \
  -d '{
        "topics": ["FinTech"],
        "language": "Klingon",
        "budget": 50,
        "sensitivity": false,
        "sla_min": 20,
        "user_id": 42
      }' | python -m json.tool
```

### 7) Capacity & Fairness Demos

```bash
# Small burst (sequential)
for i in $(seq 1 10); do
  curl -s -X POST http://localhost:8000/v1/route \
    -H 'content-type: application/json' \
    -d '{"topics":["pricing","retention"],"language":"English","budget":80,"sensitivity":false,"sla_min":25,"user_id":42}' \
    | python -m json.tool
done

curl -s http://localhost:8000/v1/state | python -m json.tool
```

```bash
# Concurrent Burst (macOS/Linux, background jobs)
for i in {1..20}; do
  curl -s -X POST http://localhost:8000/v1/route \
    -H 'content-type: application/json' \
    -d '{"topics":["payments","pricing"],"language":"English","budget":100,"sensitivity":false,"sla_min":20,"user_id":42}' &
done
wait

curl -s http://localhost:8000/v1/state | python -m json.tool
```







