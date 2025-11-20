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
        """
        self._documents_service = documents_service
        self._progress_service = progress_service
        self._graph_service = graph_service
        self._progress_db = progress_db
        self._users_db = users_db
    
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

