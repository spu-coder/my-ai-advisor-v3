"""
Service Interface Module
========================
Abstract interfaces for service communication to decouple LLM service from direct DB access.
This ensures LLM service only communicates via defined interfaces, not direct database access.

وحدة واجهة الخدمات
===================
واجهات مجردة للتواصل بين الخدمات لفصل خدمة LLM عن الوصول المباشر لقاعدة البيانات.
يضمن هذا أن خدمة LLM تتواصل فقط عبر الواجهات المحددة، وليس الوصول المباشر لقاعدة البيانات.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pydantic import BaseModel


class DocumentsServiceInterface(ABC):
    """Interface for Documents Service / واجهة خدمة المستندات"""
    
    @abstractmethod
    def retrieve_context(self, question: str) -> tuple[Optional[str], str]:
        """
        Retrieve context from documents for RAG queries.
        / استرجاع السياق من المستندات لاستعلامات RAG.
        
        Args:
            question: User question / سؤال المستخدم
            
        Returns:
            Tuple of (context_string, source_info) / مجموعة من (نص_السياق، معلومات_المصدر)
        """
        pass


class ProgressServiceInterface(ABC):
    """Interface for Progress Service / واجهة خدمة التقدم"""
    
    @abstractmethod
    async def analyze_progress(self, user_id: str) -> Dict[str, Any]:
        """
        Analyze student academic progress.
        / تحليل التقدم الأكاديمي للطالب.
        
        Args:
            user_id: Student user ID / معرف الطالب
            
        Returns:
            Dictionary with progress analysis data / قاموس يحتوي على بيانات تحليل التقدم
        """
        pass


class GraphServiceInterface(ABC):
    """Interface for Graph Service / واجهة خدمة الرسم البياني"""
    
    @abstractmethod
    def get_skills_for_course(self, course_code: str) -> List[str]:
        """
        Get skills for a specific course.
        / الحصول على المهارات لمقرر معين.
        
        Args:
            course_code: Course code / رمز المقرر
            
        Returns:
            List of skills / قائمة المهارات
        """
        pass


class ServiceAdapter:
    """
    Adapter to wrap service implementations with database sessions.
    / محول لتغليف تطبيقات الخدمات مع جلسات قاعدة البيانات.
    
    This adapter allows services to be called without exposing database sessions
    to the LLM service, maintaining proper separation of concerns.
    / يسمح هذا المحول باستدعاء الخدمات دون كشف جلسات قاعدة البيانات
    لخدمة LLM، مما يحافظ على الفصل الصحيح للاهتمامات.
    """
    
    def __init__(
        self,
        documents_service: Any,
        progress_service: Any,
        graph_service: Any,
        progress_db: Any,
        users_db: Any,
        faq_service: Optional[Any] = None,  # NEW: FAQ Service for URAG
    ):
        """
        Initialize service adapter with services and database sessions.
        / تهيئة محول الخدمات مع الخدمات وجلسات قاعدة البيانات.
        
        Args:
            documents_service: Documents service instance / مثيل خدمة المستندات
            progress_service: Progress service instance / مثيل خدمة التقدم
            graph_service: Graph service instance / مثيل خدمة الرسم البياني
            progress_db: Progress database session / جلسة قاعدة بيانات التقدم
            users_db: Users database session / جلسة قاعدة بيانات المستخدمين
            faq_service: FAQ service instance for URAG (optional) / مثيل خدمة FAQ لـ URAG (اختياري)
        """
        self._documents_service = documents_service
        self._progress_service = progress_service
        self._graph_service = graph_service
        self._progress_db = progress_db
        self._users_db = users_db
        self._faq_service = faq_service  # NEW: FAQ Service
    
    def retrieve_context(self, question: str) -> tuple[Optional[str], str]:
        """
        Retrieve context from documents service.
        / استرجاع السياق من خدمة المستندات.
        
        Args:
            question: User question / سؤال المستخدم
            
        Returns:
            Tuple of (context_string, source_info) / مجموعة من (نص_السياق، معلومات_المصدر)
        """
        return self._documents_service.retrieve_context(question)
    
    async def retrieve_context_with_urag(
        self, 
        question: str,
        metadata_context: Optional[Dict[str, Any]] = None
    ) -> tuple[Optional[str], str, Optional[Dict[str, Any]]]:
        """
        Retrieve context using URAG (Unified RAG): FAQ first, then RAG fallback.
        / استرجاع السياق باستخدام URAG (Unified RAG): FAQ أولاً، ثم RAG كاحتياطي.
        
        This implements the URAG pattern:
        1. Try FAQ matching for 100% accuracy
        2. Fallback to RAG if no FAQ match
        
        هذا يطبق نمط URAG:
        1. محاولة مطابقة FAQ لدقة 100%
        2. الرجوع إلى RAG إذا لم يتم العثور على مطابقة FAQ
        
        Args:
            question: User question / سؤال المستخدم
            metadata_context: Student context for FAQ filtering (optional)
                            / سياق الطالب لتصفية FAQ (اختياري)
        
        Returns:
            Tuple of (context_string, source_info, faq_result):
            / مجموعة من (نص_السياق، معلومات_المصدر، نتيجة_FAQ):
            - context_string: Answer or context / الإجابة أو السياق
            - source_info: Source information / معلومات المصدر
            - faq_result: FAQ match result if found, None otherwise
                         / نتيجة مطابقة FAQ إذا تم العثور عليها، None خلاف ذلك
        """
        # Step 1: Try FAQ first (for 100% accuracy)
        if self._faq_service:
            try:
                faq_result = await self._faq_service.match_faq(
                    query=question,
                    metadata_context=metadata_context
                )
                
                if faq_result:
                    # FAQ match found - return immediately
                    return (
                        faq_result["answer"],
                        f"FAQ ({faq_result['source']})",
                        faq_result
                    )
            except Exception as e:
                # Log error but continue to RAG fallback
                import logging
                logger = logging.getLogger("SERVICE_ADAPTER")
                logger.warning(f"FAQ service error, falling back to RAG: {e}")
        
        # Step 2: Fallback to RAG
        context_str, source_info = self._documents_service.retrieve_context(question)
        
        # Log RAG fallback if FAQ service is available
        if self._faq_service:
            try:
                await self._faq_service.log_rag_fallback(question)
            except Exception:
                pass  # Don't fail if logging fails
        
        return (context_str, source_info, None)
    
    async def analyze_progress(self, user_id: str) -> Dict[str, Any]:
        """
        Analyze student progress using progress service with database sessions.
        / تحليل تقدم الطالب باستخدام خدمة التقدم مع جلسات قاعدة البيانات.
        
        Args:
            user_id: Student user ID / معرف الطالب
            
        Returns:
            Dictionary with progress analysis data / قاموس يحتوي على بيانات تحليل التقدم
        """
        return await self._progress_service.analyze_progress(
            self._progress_db,
            self._users_db,
            user_id
        )
    
    def get_skills_for_course(self, course_code: str) -> List[str]:
        """
        Get skills for a course from graph service.
        / الحصول على المهارات لمقرر من خدمة الرسم البياني.
        
        Args:
            course_code: Course code / رمز المقرر
            
        Returns:
            List of skills / قائمة المهارات
        """
        return self._graph_service.get_skills_for_course(course_code)

