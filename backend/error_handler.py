"""
Comprehensive Error Handling Module
===================================
This module provides robust error handling utilities for the entire application.
Includes custom exceptions, error decorators, and comprehensive logging.

وحدة معالجة الأخطاء الشاملة
=============================
توفر هذه الوحدة أدوات معالجة أخطاء قوية للتطبيق بالكامل.
تشمل استثناءات مخصصة، مزخرفات الأخطاء، وتسجيل شامل.
"""

import logging
import traceback
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, Union, Dict
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse

logger = logging.getLogger("ERROR_HANDLER")

# Type variable for function return type
F = TypeVar('F', bound=Callable[..., Any])


# ------------------------------------------------------------
# Custom Exceptions
# ------------------------------------------------------------

class BaseApplicationException(Exception):
    """Base exception for all application-specific exceptions."""
    def __init__(self, message: str, error_code: str = "GENERIC_ERROR", details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class DocumentProcessingError(BaseApplicationException):
    """Exception raised when document processing fails."""
    def __init__(self, message: str, file_path: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "DOCUMENT_PROCESSING_ERROR", details)
        self.file_path = file_path


class OCRProcessingError(BaseApplicationException):
    """Exception raised when OCR processing fails."""
    def __init__(self, message: str, image_path: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "OCR_PROCESSING_ERROR", details)
        self.image_path = image_path


class DatabaseOperationError(BaseApplicationException):
    """Exception raised when database operations fail."""
    def __init__(self, message: str, operation: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "DATABASE_OPERATION_ERROR", details)
        self.operation = operation


class AuthenticationError(BaseApplicationException):
    """Exception raised when authentication fails."""
    def __init__(self, message: str = "Authentication failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "AUTHENTICATION_ERROR", details)


class AuthorizationError(BaseApplicationException):
    """Exception raised when authorization fails."""
    def __init__(self, message: str = "Authorization failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "AUTHORIZATION_ERROR", details)


class ValidationError(BaseApplicationException):
    """Exception raised when validation fails."""
    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "VALIDATION_ERROR", details)
        self.field = field


class ExternalServiceError(BaseApplicationException):
    """Exception raised when external service calls fail."""
    def __init__(self, message: str, service_name: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "EXTERNAL_SERVICE_ERROR", details)
        self.service_name = service_name


# ------------------------------------------------------------
# Error Handler Decorators
# ------------------------------------------------------------

def handle_errors(
    log_error: bool = True,
    return_http_exception: bool = True,
    default_status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
) -> Callable[[F], F]:
    """
    Decorator to handle errors in async functions.
    / مزخرف لمعالجة الأخطاء في الدوال غير المتزامنة.
    
    Args:
        log_error: Whether to log the error / هل يتم تسجيل الخطأ
        return_http_exception: Whether to return HTTPException / هل يتم إرجاع HTTPException
        default_status_code: Default HTTP status code / رمز حالة HTTP الافتراضي
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                # Re-raise HTTP exceptions as-is
                raise
            except BaseApplicationException as e:
                if log_error:
                    logger.error(
                        f"Application error in {func.__name__}: {e.message}",
                        extra={"error_code": e.error_code, "details": e.details},
                        exc_info=True
                    )
                if return_http_exception:
                    raise HTTPException(
                        status_code=default_status_code,
                        detail={
                            "error": e.message,
                            "error_code": e.error_code,
                            "details": e.details
                        }
                    )
                raise
            except Exception as e:
                error_msg = f"Unexpected error in {func.__name__}: {str(e)}"
                if log_error:
                    logger.error(
                        error_msg,
                        exc_info=True,
                        extra={
                            "function": func.__name__,
                            "args": str(args)[:200],  # Limit length
                            "kwargs": str(kwargs)[:200]
                        }
                    )
                if return_http_exception:
                    raise HTTPException(
                        status_code=default_status_code,
                        detail={
                            "error": "An unexpected error occurred",
                            "error_code": "UNEXPECTED_ERROR",
                            "message": str(e) if logger.level <= logging.DEBUG else "Internal server error"
                        }
                    )
                raise
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except HTTPException:
                raise
            except BaseApplicationException as e:
                if log_error:
                    logger.error(
                        f"Application error in {func.__name__}: {e.message}",
                        extra={"error_code": e.error_code, "details": e.details},
                        exc_info=True
                    )
                if return_http_exception:
                    raise HTTPException(
                        status_code=default_status_code,
                        detail={
                            "error": e.message,
                            "error_code": e.error_code,
                            "details": e.details
                        }
                    )
                raise
            except Exception as e:
                error_msg = f"Unexpected error in {func.__name__}: {str(e)}"
                if log_error:
                    logger.error(
                        error_msg,
                        exc_info=True,
                        extra={
                            "function": func.__name__,
                            "args": str(args)[:200],
                            "kwargs": str(kwargs)[:200]
                        }
                    )
                if return_http_exception:
                    raise HTTPException(
                        status_code=default_status_code,
                        detail={
                            "error": "An unexpected error occurred",
                            "error_code": "UNEXPECTED_ERROR",
                            "message": str(e) if logger.level <= logging.DEBUG else "Internal server error"
                        }
                    )
                raise
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore
    
    return decorator


def safe_execute(
    default_return: Any = None,
    log_error: bool = True,
    error_message: Optional[str] = None
) -> Callable[[F], F]:
    """
    Decorator to safely execute a function, returning default value on error.
    / مزخرف لتنفيذ دالة بأمان، وإرجاع قيمة افتراضية عند الخطأ.
    
    Args:
        default_return: Value to return on error / القيمة المرجعة عند الخطأ
        log_error: Whether to log the error / هل يتم تسجيل الخطأ
        error_message: Custom error message / رسالة خطأ مخصصة
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                msg = error_message or f"Error in {func.__name__}: {str(e)}"
                if log_error:
                    logger.warning(msg, exc_info=True)
                return default_return
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                msg = error_message or f"Error in {func.__name__}: {str(e)}"
                if log_error:
                    logger.warning(msg, exc_info=True)
                return default_return
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore
    
    return decorator


# ------------------------------------------------------------
# Error Response Helpers
# ------------------------------------------------------------

def create_error_response(
    error: Exception,
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    include_traceback: bool = False
) -> JSONResponse:
    """
    Create a standardized error response.
    / إنشاء استجابة خطأ موحدة.
    
    Args:
        error: The exception that occurred / الاستثناء الذي حدث
        status_code: HTTP status code / رمز حالة HTTP
        include_traceback: Whether to include traceback in response / هل يتم تضمين traceback في الاستجابة
        
    Returns:
        JSONResponse with error details / JSONResponse مع تفاصيل الخطأ
    """
    error_data = {
        "error": str(error),
        "error_type": type(error).__name__,
        "status_code": status_code
    }
    
    if isinstance(error, BaseApplicationException):
        error_data.update({
            "error_code": error.error_code,
            "message": error.message,
            "details": error.details
        })
    
    if include_traceback and logger.level <= logging.DEBUG:
        error_data["traceback"] = traceback.format_exc()
    
    logger.error(
        f"Error response created: {error_data}",
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status_code,
        content=error_data
    )


def log_error_with_context(
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    level: int = logging.ERROR
) -> None:
    """
    Log error with additional context.
    / تسجيل خطأ مع سياق إضافي.
    
    Args:
        error: The exception to log / الاستثناء لتسجيله
        context: Additional context dictionary / قاموس سياق إضافي
        level: Logging level / مستوى التسجيل
    """
    context = context or {}
    context.update({
        "error_type": type(error).__name__,
        "error_message": str(error)
    })
    
    logger.log(
        level,
        f"Error occurred: {error}",
        extra=context,
        exc_info=True
    )


# ------------------------------------------------------------
# Retry Decorator
# ------------------------------------------------------------

def retry_on_failure(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    log_retry: bool = True
) -> Callable[[F], F]:
    """
    Decorator to retry function on failure.
    / مزخرف لإعادة محاولة الدالة عند الفشل.
    
    Args:
        max_attempts: Maximum number of retry attempts / الحد الأقصى لعدد محاولات إعادة المحاولة
        delay: Initial delay between retries in seconds / التأخير الأولي بين المحاولات بالثواني
        backoff: Backoff multiplier / مضاعف التأخير
        exceptions: Tuple of exceptions to catch / مجموعة الاستثناءات للقبض عليها
        log_retry: Whether to log retry attempts / هل يتم تسجيل محاولات إعادة المحاولة
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        if log_retry:
                            logger.warning(
                                f"Attempt {attempt}/{max_attempts} failed for {func.__name__}: {e}. "
                                f"Retrying in {current_delay}s..."
                            )
                        import asyncio
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        if log_retry:
                            logger.error(
                                f"All {max_attempts} attempts failed for {func.__name__}"
                            )
                        raise
            
            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            import time
            current_delay = delay
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        if log_retry:
                            logger.warning(
                                f"Attempt {attempt}/{max_attempts} failed for {func.__name__}: {e}. "
                                f"Retrying in {current_delay}s..."
                            )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        if log_retry:
                            logger.error(
                                f"All {max_attempts} attempts failed for {func.__name__}"
                            )
                        raise
            
            if last_exception:
                raise last_exception
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore
    
    return decorator

