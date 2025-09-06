from __future__ import annotations

import time
import redis

DECR_LUA_SCRIPT = """
local key = KEYS[1]
local v = redis.call('GET', key)
if not v then
  redis.call('SET', key, 0)
  return 0
end
local n = tonumber(v)
if n > 0 then
  n = n - 1
  redis.call('SET', key, n)
  return n
else
  return 0
end
"""

def wait_for_redis(url: str, attempts: int = 10, base_sleep: float = 0.3) -> redis.Redis:
    client = redis.Redis.from_url(url, decode_responses=True)
    for i in range(attempts):
        try:
            client.ping()
            return client
        except Exception:
            time.sleep(base_sleep * (2**i))
    raise RuntimeError(f"Redis not reachable at {url}")

def register_decr_lua(r: redis.Redis):
    return r.register_script(DECR_LUA_SCRIPT)

def get_q(r: redis.Redis, interviewer_id: int) -> int:
    return int(r.get(f"interviewer:{interviewer_id}:queue") or 0)
