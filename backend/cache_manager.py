"""
Cache Manager
============
Centralized cache abstraction that prefers Redis and falls back to an
in-memory TTL cache. Used by security, RAG, and LLM layers to avoid
repeated heavy work.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, Optional

try:  # pragma: no cover - optional dependency
    import redis  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    redis = None  # type: ignore


class _InMemoryTTLCache:
    """
    Lightweight thread-safe TTL cache as a Redis fallback.
    / تخزين مؤقت خفيف آمن للخيوط مع TTL كبديل لـ Redis.
    """

    def __init__(self) -> None:
        """Initialize in-memory TTL cache / تهيئة تخزين مؤقت TTL في الذاكرة"""
        self._store: Dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache by key.
        / الحصول على قيمة من التخزين المؤقت باستخدام المفتاح.
        
        Args:
            key: Cache key / مفتاح التخزين المؤقت
            
        Returns:
            Cached value or None if not found/expired / القيمة المخزنة أو None إذا لم تُعثر أو انتهت صلاحيتها
        """
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            expires_at, value = entry
            if expires_at < time.time():
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        """
        Set value in cache with TTL.
        / تعيين قيمة في التخزين المؤقت مع TTL.
        
        Args:
            key: Cache key / مفتاح التخزين المؤقت
            value: Value to cache / القيمة للتخزين المؤقت
            ttl_seconds: Time to live in seconds / وقت البقاء بالثواني
        """
        expires_at = time.time() + ttl_seconds
        with self._lock:
            self._store[key] = (expires_at, value)


class CacheManager:
    """
    Simple cache facade with optional Redis backend.
    / واجهة تخزين مؤقت بسيطة مع خلفية Redis اختيارية.
    """

    def __init__(self) -> None:
        """
        Initialize cache manager with Redis or in-memory fallback.
        / تهيئة مدير التخزين المؤقت مع Redis أو بديل في الذاكرة.
        """
        redis_url = os.getenv("REDIS_CACHE_URL") or os.getenv("RATE_LIMIT_REDIS_URL")
        self._redis_client = None
        if redis_url and redis:
            try:
                self._redis_client = redis.Redis.from_url(redis_url)
            except Exception:  # pragma: no cover - connection failure
                self._redis_client = None
        self._fallback_cache = _InMemoryTTLCache()

    def _serialize(self, value: Any) -> str:
        """
        Serialize value for caching.
        / تحويل القيمة إلى صيغة قابلة للتخزين المؤقت.
        
        Args:
            value: Value to serialize / القيمة للتحويل
            
        Returns:
            Serialized string / سلسلة محولة
        """
        if isinstance(value, (str, bytes)):
            return value if isinstance(value, str) else value.decode("utf-8")
        return json.dumps(value, ensure_ascii=False)

    def _deserialize(self, cached: Optional[bytes | str]) -> Optional[Any]:
        """
        Deserialize cached value.
        / تحويل القيمة المخزنة مؤقتاً إلى صيغتها الأصلية.
        
        Args:
            cached: Cached value (bytes or string) / القيمة المخزنة (بايت أو سلسلة)
            
        Returns:
            Deserialized value or None / القيمة المحولة أو None
        """
        if cached is None:
            return None
        if isinstance(cached, bytes):
            cached = cached.decode("utf-8")
        try:
            return json.loads(cached)
        except json.JSONDecodeError:
            return cached

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache (Redis or in-memory).
        / الحصول على قيمة من التخزين المؤقت (Redis أو في الذاكرة).
        
        Args:
            key: Cache key / مفتاح التخزين المؤقت
            
        Returns:
            Cached value or None / القيمة المخزنة أو None
        """
        if self._redis_client:
            try:
                cached = self._redis_client.get(key)
                if cached is not None:
                    return self._deserialize(cached)
            except Exception:
                pass  # fallback below
        cached = self._fallback_cache.get(key)
        return cached

    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        """
        Set value in cache with TTL (Redis or in-memory).
        / تعيين قيمة في التخزين المؤقت مع TTL (Redis أو في الذاكرة).
        
        Args:
            key: Cache key / مفتاح التخزين المؤقت
            value: Value to cache / القيمة للتخزين المؤقت
            ttl_seconds: Time to live in seconds (default: 300) / وقت البقاء بالثواني (افتراضي: 300)
        """
        serialized = self._serialize(value)
        if self._redis_client:
            try:
                self._redis_client.setex(key, ttl_seconds, serialized)
                return
            except Exception:
                pass
        self._fallback_cache.set(key, serialized, ttl_seconds)


cache_manager = CacheManager()


