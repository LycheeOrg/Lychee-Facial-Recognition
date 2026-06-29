"""Redis-backed job queue.

Uses a Redis list as the queue (RPUSH to enqueue, LPOP to dequeue) and a
Redis hash to track in-flight jobs so that ``position()`` can distinguish
between "pending", "processing", and "done".

Key layout:
  queue:jobs            - List of JSON job payloads (FIFO: enqueue=RPUSH, dequeue=LPOP)
  queue:inflight        - Hash  {job_id -> json} for in-flight tracking
  queue:counter         - String auto-increment id (INCR)
"""

from __future__ import annotations

import json
from typing import Any

from app.queue.base import Job


class RedisJobQueue:
    """Job queue backed by Redis."""

    _JOBS_KEY = "queue:jobs"
    _INFLIGHT_KEY = "queue:inflight"
    _COUNTER_KEY = "queue:counter"

    def __init__(
        self,
        host: str,
        port: int,
        password: str,
        db: int,
        max_size: int,
    ) -> None:
        import redis

        self._redis: Any = redis.Redis(
            host=host,
            port=port,
            password=password or None,
            db=db,
            decode_responses=True,
        )
        self._max_size = max_size

    # ------------------------------------------------------------------
    # JobQueue protocol
    # ------------------------------------------------------------------

    _ENQUEUE_IF_IDLE_SCRIPT = """
    local pending = redis.call('LLEN', KEYS[1])
    local inflight = redis.call('HLEN', KEYS[2])
    if pending + inflight > 0 then
        return 0
    end
    local job_id = redis.call('INCR', KEYS[3])
    local item = cjson.encode({id=job_id, job_type=ARGV[1], photo_id=ARGV[2], payload=ARGV[3]})
    redis.call('RPUSH', KEYS[1], item)
    return 1
    """

    async def enqueue(self, job_type: str, photo_id: str, payload: str) -> bool:
        r = self._redis
        if r.llen(self._JOBS_KEY) >= self._max_size and self._max_size > 0:
            return False
        job_id = r.incr(self._COUNTER_KEY)
        item = json.dumps({"id": job_id, "job_type": job_type, "photo_id": photo_id, "payload": payload})
        r.rpush(self._JOBS_KEY, item)
        return True

    async def enqueue_if_idle(self, job_type: str, photo_id: str, payload: str) -> bool:
        r = self._redis
        script = r.register_script(self._ENQUEUE_IF_IDLE_SCRIPT)
        result = script(
            keys=[self._JOBS_KEY, self._INFLIGHT_KEY, self._COUNTER_KEY],
            args=[job_type, photo_id, payload],
        )
        return int(result) == 1

    async def dequeue(self) -> Job | None:
        r = self._redis
        raw = r.lpop(self._JOBS_KEY)
        if raw is None:
            return None
        data = json.loads(raw)
        job = Job(
            id=int(data["id"]),
            job_type=data["job_type"],
            photo_id=data["photo_id"],
            payload=data["payload"],
        )
        # Track in-flight so position() can report status = "processing".
        r.hset(self._INFLIGHT_KEY, str(job.id), raw)
        return job

    async def complete(self, job_id: int) -> None:
        self._redis.hdel(self._INFLIGHT_KEY, str(job_id))

    async def size(self) -> int:
        return int(self._redis.llen(self._JOBS_KEY))

    async def purge(self) -> None:
        self._redis.delete(self._JOBS_KEY)

    async def position(self, photo_id: str) -> int | None:
        r = self._redis
        # Check in-flight first (position 0 = currently processing).
        for raw in r.hvals(self._INFLIGHT_KEY):
            data = json.loads(raw)
            if data.get("photo_id") == photo_id:
                return 0

        # Scan the pending list for the photo_id.
        items = r.lrange(self._JOBS_KEY, 0, -1)
        for idx, raw in enumerate(items):
            data = json.loads(raw)
            if data.get("photo_id") == photo_id:
                return idx + 1  # 1-based rank

        return None  # absent = done

    async def close(self) -> None:
        self._redis.close()
