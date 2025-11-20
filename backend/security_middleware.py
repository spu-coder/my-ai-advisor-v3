"""
Security Middleware Module
==========================
This module implements OWASP security best practices including:
- Rate limiting
- Security headers
- Input validation and sanitization
- Request size limits
- SQL injection prevention helpers

وحدة أمان الوسطاء
==================
هذه الوحدة تطبق أفضل ممارسات أمان OWASP بما في ذلك:
- تحديد معدل الطلبات
- رؤوس الأمان
- التحقق من المدخلات وتنظيفها
- حدود حجم الطلب
- مساعدات منع حقن SQL
"""

import os
import time
import re
import json
import logging
from collections import defaultdict
from typing import Dict, Tuple, Sequence

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

try:
    import redis.asyncio as aioredis
except ImportError:  # pragma: no cover - fallback if redis not installed
    aioredis = None

logger = logging.getLogger("SECURITY_MIDDLEWARE")

# ------------------------------------------------------------
# Rate Limiting Configuration
# إعدادات تحديد معدل الطلبات
# ------------------------------------------------------------
RATE_LIMIT_WINDOW = 60  # seconds / ثواني
RATE_LIMIT_MAX_REQUESTS = 100  # requests per window / طلبات لكل نافذة
RATE_LIMIT_AUTH_MAX = 10  # login attempts per window / محاولات تسجيل دخول لكل نافذة
RATE_LIMIT_REDIS_URL = os.getenv("RATE_LIMIT_REDIS_URL")


class RedisRateLimiter:
    """داعم تحديد المعدل باستخدام Redis مع دعم احتياطي في الذاكرة."""

    def __init__(self):
        self._redis_url = RATE_LIMIT_REDIS_URL
        self._redis = None
        if self._redis_url and aioredis:
            try:
                self._redis = aioredis.from_url(
                    self._redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )
                logger.info("Rate limiter using Redis backend.")
            except Exception as exc:  # pragma: no cover - network failure
                logger.warning(f"Unable to connect to Redis rate limiter: {exc}")
                self._redis = None
        else:
            if not aioredis:
                logger.warning("redis package not available; falling back to in-memory rate limiting.")
        self._local_counts: Dict[str, list] = defaultdict(list)

    async def _redis_check(self, key: str, limit: int, window: int) -> bool:
        if not self._redis:
            return True
        try:
            current = await self._redis.incr(key)
            if current == 1:
                await self._redis.expire(key, window)
            if current > limit:
                return False
            return True
        except Exception as exc:  # pragma: no cover - redis failure
            logger.error(f"Redis rate limiter error: {exc}. Falling back to in-memory limiter.")
            self._redis = None
            return True

    def _local_check(self, key: str, limit: int, window: int) -> bool:
        current_time = time.time()
        bucket = self._local_counts[key]
        self._local_counts[key] = [req_time for req_time in bucket if current_time - req_time < window]
        if len(self._local_counts[key]) >= limit:
            return False
        self._local_counts[key].append(current_time)
        return True

    async def is_allowed(self, key: str, limit: int, window: int) -> bool:
        if self._redis:
            allowed = await self._redis_check(key, limit, window)
            if not allowed:
                return False
        return self._local_check(key, limit, window)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware to prevent abuse.
    / وسطاء تحديد معدل الطلبات لمنع إساءة الاستخدام.
    """
    
    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        limiter = self.rate_limiter
        
        # Check rate limit for authentication endpoints
        # التحقق من حد المعدل لمسارات المصادقة
        if path in ["/token", "/token/json", "/register/student", "/register/admin"]:
            allowed = await limiter.is_allowed(
                key=f"auth:{client_ip}",
                limit=RATE_LIMIT_AUTH_MAX,
                window=RATE_LIMIT_WINDOW,
            )
            if not allowed:
                logger.warning(f"Rate limit exceeded for auth endpoint from IP: {client_ip}")
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": "Too many authentication attempts. Please try again later.",
                        "error_ar": "عدد كبير جداً من محاولات المصادقة. يرجى المحاولة لاحقاً."
                    }
                )
        
        # Check general rate limit
        # التحقق من حد المعدل العام
        allowed = await limiter.is_allowed(
            key=f"req:{client_ip}",
            limit=RATE_LIMIT_MAX_REQUESTS,
            window=RATE_LIMIT_WINDOW,
        )
        if not allowed:
            logger.warning(f"Rate limit exceeded from IP: {client_ip}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Too many requests. Please try again later.",
                    "error_ar": "عدد كبير جداً من الطلبات. يرجى المحاولة لاحقاً."
                }
            )
        
        response = await call_next(request)
        return response

    @property
    def rate_limiter(self) -> RedisRateLimiter:
        if not hasattr(self, "_rate_limiter"):
            self._rate_limiter = RedisRateLimiter()
        return self._rate_limiter


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses (OWASP best practices).
    / إضافة رؤوس الأمان لجميع الاستجابات (أفضل ممارسات OWASP).
    """
    
    async def dispatch(self, request: Request, call_next):
        """Add security headers to response."""
        response = await call_next(request)
        
        # OWASP recommended security headers
        # رؤوس الأمان الموصى بها من OWASP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        return response


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """
    Authenticate JWT before heavy processing to avoid resource exhaustion.
    """

    def __init__(self, app, protected_paths: Sequence[str] | None = None):
        super().__init__(app)
        self.protected_paths = protected_paths or []
        self.excluded_paths = {
            "/token",
            "/token/json",
            "/register/student",
            "/register/admin",
            "/register/admin/initial",
            "/health",
            "/docs",
            "/openapi.json",
        }

    def _requires_auth(self, path: str) -> bool:
        if path in self.excluded_paths:
            return False
        return any(path.startswith(prefix) for prefix in self.protected_paths)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not self._requires_auth(path):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.lower().startswith("bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "Authorization header missing or invalid.",
                    "error_ar": "رمز المصادقة مفقود أو غير صالح.",
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = auth_header.split(" ", 1)[1].strip()
        try:
            from security import decode_access_token  # استيراد متأخر لتجنب الحلقات

            token_data = decode_access_token(token)
            request.state.token_data = {
                "user_id": token_data[0],
                "is_demo": token_data[1],
                "raw_token": token,
            }
        except Exception as exc:
            logger.warning(f"JWT authentication failed for path {path}: {exc}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "Invalid or expired token",
                    "error_ar": "الرمز غير صالح أو منتهي الصلاحية",
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)


class WAFMiddleware(BaseHTTPMiddleware):
    """
    Lightweight Web Application Firewall middleware.
    Blocks obvious malicious payloads before they reach the app.
    """

    SUSPICIOUS_PATTERNS = [
        re.compile(pattern, re.IGNORECASE)
        for pattern in [
            r"(\bUNION\b|\bSELECT\b).+\bFROM\b",
            r"(<script|</script>)",
            r"\b(drop|alter|truncate)\b",
            r"\b(or|and)\b\s+1=1",
            r"base64_decode\(",
        ]
    ]
    BLOCKED_USER_AGENTS = {"sqlmap", "curl", "wget"}

    async def dispatch(self, request: Request, call_next):
        user_agent = request.headers.get("user-agent", "").lower()
        if any(agent in user_agent for agent in self.BLOCKED_USER_AGENTS):
            logger.warning("Blocked request due to suspicious user-agent: %s", user_agent)
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Forbidden", "error_ar": "تم حظر الطلب"}
            )

        body_preview = ""
        if request.method in {"POST", "PUT", "PATCH"}:
            body = await request.body()
            if body:
                try:
                    body_preview = body.decode("utf-8", errors="ignore")[:500]
                except Exception:
                    body_preview = ""
                request._body = body  # re-set body for downstream consumers

        haystack = " ".join([
            request.url.path,
            request.url.query or "",
            body_preview,
        ])
        if any(pattern.search(haystack) for pattern in self.SUSPICIOUS_PATTERNS):
            logger.warning("Blocked request by WAF pattern match: %s", request.url.path)
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Potentially malicious payload blocked."}
            )

        return await call_next(request)


class InputSanitizationMiddleware(BaseHTTPMiddleware):
    """
    Sanitize inputs after authentication to avoid wasting resources on unauthenticated users.
    """

    async def dispatch(self, request: Request, call_next):

        def _sanitize_payload(payload):
            if isinstance(payload, str):
                return sanitize_string(payload, max_length=4000)
            if isinstance(payload, list):
                return [_sanitize_payload(item) for item in payload]
            if isinstance(payload, dict):
                return {key: _sanitize_payload(value) for key, value in payload.items()}
            return payload

        sanitized_query = {}
        for key, value in request.query_params.multi_items():
            sanitized_query[key] = sanitize_string(value, max_length=2000)
        request.state.sanitized_query = sanitized_query

        if request.method in {"POST", "PUT", "PATCH"}:
            raw_body = await request.body()
            if raw_body:
                try:
                    payload = json.loads(raw_body)
                    sanitized_payload = _sanitize_payload(payload)
                    request.state.sanitized_body = sanitized_payload
                    request._body = json.dumps(sanitized_payload).encode("utf-8")
                except json.JSONDecodeError:
                    try:
                        sanitized_text = sanitize_string(raw_body.decode("utf-8", errors="ignore"), max_length=MAX_REQUEST_SIZE)
                        request._body = sanitized_text.encode("utf-8")
                    except Exception:
                        request._body = raw_body
            else:
                request._body = raw_body
        return await call_next(request)


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """
    Auditing middleware that captures request/response metadata for forensics.
    """

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        client_ip = request.client.host if request.client else "unknown"
        response = await call_next(request)
        duration_ms = int((time.time() - start_time) * 1000)
        audit_entry = {
            "path": request.url.path,
            "method": request.method,
            "status": response.status_code,
            "ip": client_ip,
            "duration_ms": duration_ms,
        }
        logger.info("AUDIT_LOG %s", audit_entry)
        return response


# ------------------------------------------------------------
# Input Validation and Sanitization
# التحقق من المدخلات وتنظيفها
# ------------------------------------------------------------

def sanitize_string(input_str: str, max_length: int = 1000) -> str:
    """
    Sanitize string input to prevent injection attacks.
    / تنظيف إدخال النص لمنع هجمات الحقن.
    
    Args:
        input_str: Input string to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized string
    """
    if not isinstance(input_str, str):
        raise ValueError("Input must be a string")
    
    # Remove null bytes
    input_str = input_str.replace('\x00', '')
    
    # Limit length
    if len(input_str) > max_length:
        input_str = input_str[:max_length]
    
    # Remove potentially dangerous characters (basic)
    # Note: This is basic sanitization. For production, use proper escaping
    # ملاحظة: هذا تنظيف أساسي. للإنتاج، استخدم التهريب المناسب
    dangerous_chars = ['<', '>', '"', "'", '&']
    for char in dangerous_chars:
        input_str = input_str.replace(char, '')
    
    return input_str.strip()


def validate_user_id(user_id: str) -> bool:
    """
    Validate user ID format (alphanumeric and underscores only).
    / التحقق من تنسيق معرف المستخدم (أرقام وحروف وشرطة سفلية فقط).
    """
    if not user_id or len(user_id) > 50:
        return False
    return bool(re.match(r'^[a-zA-Z0-9_]+$', user_id))


def validate_email(email: str) -> bool:
    """
    Validate email format.
    / التحقق من تنسيق البريد الإلكتروني.
    """
    if not email or len(email) > 255:
        return False
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_pattern, email))


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Validate password strength.
    / التحقق من قوة كلمة المرور.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(password) < 6:
        return False, "Password must be at least 6 characters long"
    
    if len(password) > 128:
        return False, "Password is too long (max 128 characters)"
    
    # Check for common weak passwords
    # التحقق من كلمات المرور الضعيفة الشائعة
    weak_passwords = ['password', '123456', 'admin', 'qwerty']
    if password.lower() in weak_passwords:
        return False, "Password is too weak. Please choose a stronger password."
    
    return True, ""


def sanitize_sql_input(input_str: str) -> str:
    """
    Basic SQL injection prevention (use parameterized queries instead).
    / منع حقن SQL الأساسي (استخدم استعلامات معاملات بدلاً من ذلك).
    
    WARNING: This is a basic check. Always use parameterized queries!
    / تحذير: هذا فحص أساسي. استخدم دائماً استعلامات معاملات!
    """
    if not isinstance(input_str, str):
        return ""
    
    # Remove SQL keywords that could be used in injection
    # إزالة كلمات SQL الرئيسية التي يمكن استخدامها في الحقن
    sql_keywords = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'EXEC', 'EXECUTE', 'UNION']
    sanitized = input_str
    for keyword in sql_keywords:
        # Case-insensitive replacement
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        sanitized = pattern.sub('', sanitized)
    
    return sanitized.strip()


# ------------------------------------------------------------
# Request Size Limiting
# تحديد حجم الطلب
# ------------------------------------------------------------

MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10 MB


class RequestSizeMiddleware(BaseHTTPMiddleware):
    """
    Limit request body size to prevent DoS attacks.
    / تحديد حجم جسم الطلب لمنع هجمات DoS.
    """
    
    async def dispatch(self, request: Request, call_next):
        """Check request size before processing."""
        if request.method in ["POST", "PUT", "PATCH"]:
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    size = int(content_length)
                    if size > MAX_REQUEST_SIZE:
                        logger.warning(f"Request size {size} exceeds limit {MAX_REQUEST_SIZE}")
                        return JSONResponse(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            content={
                                "detail": f"Request too large. Maximum size is {MAX_REQUEST_SIZE / 1024 / 1024} MB",
                                "error_ar": f"الطلب كبير جداً. الحد الأقصى للحجم هو {MAX_REQUEST_SIZE / 1024 / 1024} ميجابايت"
                            }
                        )
                except ValueError:
                    pass
        
        response = await call_next(request)
        return response

