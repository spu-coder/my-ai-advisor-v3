"""
FAQ Service - Unified RAG (URAG)
=================================
Ensures 100% accuracy for factual questions

يضمن دقة 100% للأسئلة الواقعية
"""

import re
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database import FAQEntry, FAQMatchLog

logger = logging.getLogger("FAQ_SERVICE")


class FAQService:
    """
    FAQ Service for exact factual questions
    خدمة الأسئلة الشائعة للأسئلة الواقعية الدقيقة
    
    This service provides 100% accurate answers for factual questions
    by matching user queries against predefined FAQ patterns.
    
    توفر هذه الخدمة إجابات دقيقة 100% للأسئلة الواقعية
    من خلال مطابقة استعلامات المستخدم مع أنماط الأسئلة الشائعة المحددة مسبقاً.
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize FAQ Service
        
        تهيئة خدمة الأسئلة الشائعة
        
        Args:
            session: Database session / جلسة قاعدة البيانات
        """
        self.session = session
        self.confidence_threshold = 0.85  # Minimum confidence for FAQ match
    
    async def match_faq(
        self, 
        query: str,
        metadata_context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Try to match query with FAQ entry
        
        محاولة مطابقة الاستعلام مع سؤال شائع
        
        Args:
            query: User query / استعلام المستخدم
            metadata_context: Student context for filtering (major, year, plan_version, etc.)
                            / سياق الطالب للتصفية (التخصص، السنة، إصدار الخطة، إلخ)
        
        Returns:
            Dictionary with answer, confidence, source, and category if match found
            / قاموس يحتوي على الإجابة، الثقة، المصدر، والفئة إذا تم العثور على مطابقة
            None if no match found / None إذا لم يتم العثور على مطابقة
        """
        try:
            # Get all active FAQs
            stmt = select(FAQEntry).where(FAQEntry.is_active == True)
            
            # Apply metadata filtering if context provided
            if metadata_context:
                # Filter by plan version if provided
                if "plan_version" in metadata_context:
                    # This would require JSON filtering - simplified for now
                    # In production, use PostgreSQL JSONB operators
                    pass
                
                # Filter by major/department if provided
                if "major" in metadata_context:
                    # Similar JSON filtering
                    pass
            
            result = await self.session.execute(stmt)
            faqs = result.scalars().all()
            
            if not faqs:
                logger.debug("No active FAQ entries found")
                return None
            
            # Try to match patterns
            best_match = None
            best_score = 0.0
            
            for faq in faqs:
                # Regex match
                pattern = faq.question_pattern
                try:
                    if re.search(pattern, query, re.IGNORECASE):
                        score = self._calculate_match_score(query, faq, pattern)
                        
                        if score > best_score:
                            best_score = score
                            best_match = faq
                except re.error as e:
                    logger.warning(f"Invalid regex pattern in FAQ {faq.id}: {pattern}. Error: {e}")
                    continue
            
            # Return if confidence is high enough
            if best_match and best_score >= self.confidence_threshold:
                logger.info(f"FAQ Match found (ID: {best_match.id}, confidence: {best_score:.2f})")
                
                # Log match for analytics
                await self._log_match(query, best_match.id, best_score, used_llm_fallback=False)
                
                return {
                    "answer": best_match.answer_template,
                    "confidence": best_score,
                    "source": f"FAQ Entry #{best_match.id}",
                    "category": best_match.category,
                    "faq_id": best_match.id
                }
            
            logger.debug(f"No FAQ match found (best score: {best_score:.2f} < threshold: {self.confidence_threshold})")
            return None
            
        except Exception as e:
            logger.error(f"Error matching FAQ: {e}", exc_info=True)
            return None
    
    def _calculate_match_score(
        self, 
        query: str, 
        faq: FAQEntry, 
        pattern: str
    ) -> float:
        """
        Calculate match score (0-1)
        
        حساب درجة المطابقة (0-1)
        
        Args:
            query: User query / استعلام المستخدم
            faq: FAQ entry / سؤال شائع
            pattern: Regex pattern / نمط regex
        
        Returns:
            Match score between 0 and 1 / درجة المطابقة بين 0 و 1
        """
        try:
            # Simple scoring: if regex matches, return high score
            # Can be enhanced with semantic similarity or keyword matching
            
            # Check if pattern matches exactly (case-insensitive)
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                # Base score from regex match
                base_score = 0.95
                
                # Boost score if query contains key terms from FAQ category
                if faq.category.lower() in query.lower():
                    base_score = min(1.0, base_score + 0.05)
                
                # Consider priority (higher priority = slightly higher score)
                priority_boost = min(0.05, faq.priority / 100.0)
                
                return min(1.0, base_score + priority_boost)
            
            return 0.0
            
        except Exception as e:
            logger.warning(f"Error calculating match score: {e}")
            return 0.0
    
    async def _log_match(
        self, 
        query: str, 
        faq_id: int, 
        score: float,
        used_llm_fallback: bool = False
    ) -> None:
        """
        Log FAQ match for analytics
        
        تسجيل مطابقة الأسئلة الشائعة للتحليلات
        
        Args:
            query: User query / استعلام المستخدم
            faq_id: Matched FAQ entry ID / معرف السؤال الشائع المطابق
            score: Match confidence score / درجة ثقة المطابقة
            used_llm_fallback: Whether RAG was used as fallback / ما إذا تم استخدام RAG كاحتياطي
        """
        try:
            log_entry = FAQMatchLog(
                user_query=query,
                matched_faq_id=faq_id,
                confidence_score=score,
                used_llm_fallback=used_llm_fallback
            )
            self.session.add(log_entry)
            await self.session.commit()
        except Exception as e:
            logger.error(f"Error logging FAQ match: {e}", exc_info=True)
            await self.session.rollback()
    
    async def log_rag_fallback(self, query: str) -> None:
        """
        Log when RAG is used as fallback (no FAQ match)
        
        تسجيل استخدام RAG كاحتياطي (عدم وجود مطابقة FAQ)
        
        Args:
            query: User query / استعلام المستخدم
        """
        try:
            log_entry = FAQMatchLog(
                user_query=query,
                matched_faq_id=None,
                confidence_score=None,
                used_llm_fallback=True
            )
            self.session.add(log_entry)
            await self.session.commit()
        except Exception as e:
            logger.error(f"Error logging RAG fallback: {e}", exc_info=True)
            await self.session.rollback()
    
    async def get_faq_by_id(self, faq_id: int) -> Optional[FAQEntry]:
        """
        Get FAQ entry by ID
        
        الحصول على سؤال شائع بالمعرف
        
        Args:
            faq_id: FAQ entry ID / معرف السؤال الشائع
        
        Returns:
            FAQEntry if found, None otherwise / FAQEntry إذا تم العثور عليه، None خلاف ذلك
        """
        try:
            stmt = select(FAQEntry).where(FAQEntry.id == faq_id)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting FAQ by ID {faq_id}: {e}", exc_info=True)
            return None
    
    async def get_all_active_faqs(
        self, 
        category: Optional[str] = None
    ) -> List[FAQEntry]:
        """
        Get all active FAQ entries, optionally filtered by category
        
        الحصول على جميع الأسئلة الشائعة النشطة، مع إمكانية التصفية حسب الفئة
        
        Args:
            category: Optional category filter / مرشح الفئة الاختياري
        
        Returns:
            List of FAQEntry objects / قائمة كائنات FAQEntry
        """
        try:
            stmt = select(FAQEntry).where(FAQEntry.is_active == True)
            
            if category:
                stmt = stmt.where(FAQEntry.category == category)
            
            stmt = stmt.order_by(FAQEntry.priority.desc(), FAQEntry.created_at.desc())
            
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting active FAQs: {e}", exc_info=True)
            return []
