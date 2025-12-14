"""
Advisor Alert Service
====================
Advisor-in-the-Loop implementation

تطبيق المرشد-في-الحلقة
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import AdvisorAlert, Intervention, User

logger = logging.getLogger("ADVISOR_ALERT_SERVICE")


class AdvisorAlertService:
    """
    Manages advisor alerts and interventions
    إدارة تنبيهات المرشد والتدخلات
    
    This service implements the Advisor-in-the-Loop pattern where human advisors
    review AI predictions before they are sent to students.
    
    تطبق هذه الخدمة نمط المرشد-في-الحلقة حيث يراجع المرشدون البشريون
    تنبؤات الذكاء الاصطناعي قبل إرسالها للطلاب.
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize Advisor Alert Service
        
        تهيئة خدمة تنبيهات المرشد
        
        Args:
            session: Database session / جلسة قاعدة البيانات
        """
        self.session = session
    
    async def generate_alert_from_prediction(
        self,
        student_id: str,
        prediction_result: Dict[str, Any]
    ) -> AdvisorAlert:
        """
        Convert prediction to advisor alert
        
        تحويل التنبؤ إلى تنبيه للمرشد
        
        Args:
            student_id: Student user ID / معرف الطالب
            prediction_result: Prediction result dictionary containing:
                            / قاموس نتيجة التنبؤ يحتوي على:
                - risk_level: "low", "medium", "high", "critical"
                - probability: Confidence score (0-1)
                - feature_importance: Dict of contributing factors
                - description: Optional human-readable description
        
        Returns:
            Created AdvisorAlert object / كائن AdvisorAlert المنشأ
        """
        try:
            # Generate alert description if not provided
            description = prediction_result.get("description")
            if not description:
                description = self._generate_alert_description(prediction_result)
            
            # Create alert
            alert = AdvisorAlert(
                student_id=student_id,
                alert_type=prediction_result.get("alert_type", "academic_risk"),
                risk_level=prediction_result["risk_level"],
                description=description,
                contributing_factors=prediction_result.get("feature_importance", {}),
                prediction_confidence=prediction_result.get("probability", 0.0),
                status="pending"
            )
            
            self.session.add(alert)
            await self.session.commit()
            await self.session.refresh(alert)
            
            logger.info(f"Created advisor alert {alert.id} for student {student_id} (risk: {prediction_result['risk_level']})")
            
            return alert
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating advisor alert: {e}", exc_info=True)
            raise
    
    def _generate_alert_description(self, prediction: Dict[str, Any]) -> str:
        """
        Generate human-readable alert description
        
        توليد وصف مقروء للتنبيه
        
        Args:
            prediction: Prediction result dictionary / قاموس نتيجة التنبؤ
        
        Returns:
            Human-readable description / وصف مقروء
        """
        risk_level = prediction.get("risk_level", "unknown")
        probability = prediction.get("probability", 0.0)
        
        description = f"الطالب في مستوى خطر {risk_level} (ثقة التنبؤ: {probability*100:.1f}%).\n\n"
        
        # Get top 3 contributing factors
        factors = prediction.get("feature_importance", {})
        if factors:
            description += "العوامل المساهمة الرئيسية:\n"
            top_factors = sorted(factors.items(), key=lambda x: x[1], reverse=True)[:3]
            
            for factor, importance in top_factors:
                percentage = importance * 100
                factor_name_ar = self._translate_factor(factor)
                description += f"- {factor_name_ar}: {percentage:.1f}%\n"
        
        return description
    
    def _translate_factor(self, factor: str) -> str:
        """
        Translate factor name to Arabic
        
        ترجمة اسم العامل إلى العربية
        
        Args:
            factor: Factor name in English / اسم العامل بالإنجليزية
        
        Returns:
            Arabic translation / الترجمة العربية
        """
        translations = {
            "low_attendance": "انخفاض الحضور",
            "poor_prereq_grade": "درجة ضعيفة في المتطلب السابق",
            "low_lms_activity": "انخفاض النشاط في نظام إدارة التعلم",
            "declining_gpa": "انخفاض المعدل التراكمي",
            "late_submissions": "تسليم متأخر للواجبات",
            "social_withdrawal": "انسحاب اجتماعي",
            "submission_pattern_change": "تغيير في نمط التسليم",
            "session_duration_drop": "انخفاض مدة الجلسات",
            "late_night_activity_spike": "زيادة النشاط الليلي"
        }
        
        return translations.get(factor, factor)
    
    async def get_pending_alerts(
        self,
        advisor_id: Optional[str] = None,
        priority: Optional[str] = None,
        limit: int = 50
    ) -> List[AdvisorAlert]:
        """
        Get pending alerts for advisor review
        
        الحصول على التنبيهات المعلّقة للمراجعة
        
        Args:
            advisor_id: Optional advisor ID to filter by assigned advisor
                       / معرف المرشد الاختياري للتصفية حسب المرشد المعين
            priority: Optional priority filter ("high", "medium", "low", "critical")
                     / مرشح الأولوية الاختياري
            limit: Maximum number of alerts to return / الحد الأقصى لعدد التنبيهات
        
        Returns:
            List of AdvisorAlert objects ordered by risk level
            / قائمة كائنات AdvisorAlert مرتبة حسب مستوى الخطر
        """
        try:
            # Build query
            stmt = select(AdvisorAlert).where(AdvisorAlert.status == "pending")
            
            # Filter by advisor if provided
            if advisor_id:
                stmt = stmt.where(
                    or_(
                        AdvisorAlert.advisor_id == advisor_id,
                        AdvisorAlert.advisor_id.is_(None)  # Unassigned alerts
                    )
                )
            
            # Filter by priority/risk level if provided
            if priority:
                stmt = stmt.where(AdvisorAlert.risk_level == priority)
            
            # Order by risk level (critical → high → medium → low)
            risk_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
            stmt = stmt.order_by(
                AdvisorAlert.risk_level.desc(),  # Simple ordering
                AdvisorAlert.created_at.desc()
            )
            
            # Limit results
            stmt = stmt.limit(limit)
            
            # Load relationships
            stmt = stmt.options(
                selectinload(AdvisorAlert.student),
                selectinload(AdvisorAlert.advisor)
            )
            
            result = await self.session.execute(stmt)
            alerts = result.scalars().all()
            
            # Sort by risk level manually for better ordering
            alerts_sorted = sorted(
                alerts,
                key=lambda a: risk_order.get(a.risk_level, 0),
                reverse=True
            )
            
            logger.info(f"Retrieved {len(alerts_sorted)} pending alerts")
            
            return alerts_sorted
            
        except Exception as e:
            logger.error(f"Error getting pending alerts: {e}", exc_info=True)
            return []
    
    async def action_alert(
        self,
        alert_id: int,
        advisor_id: str,
        action_type: str,
        notes: str,
        scheduled_at: Optional[datetime] = None
    ) -> Intervention:
        """
        Record advisor action on alert
        
        تسجيل إجراء المرشد على التنبيه
        
        Args:
            alert_id: Alert ID / معرف التنبيه
            advisor_id: Advisor user ID / معرف المرشد
            action_type: Type of intervention ("email", "meeting", "resource_suggestion", "dismiss")
                        / نوع التدخل
            notes: Advisor's notes / ملاحظات المرشد
            scheduled_at: Optional scheduled time for intervention
                         / وقت مجدول للتدخل (اختياري)
        
        Returns:
            Created Intervention object / كائن Intervention المنشأ
        
        Raises:
            ValueError: If alert not found or invalid action type
        """
        try:
            # Get alert
            stmt = select(AdvisorAlert).where(AdvisorAlert.id == alert_id)
            result = await self.session.execute(stmt)
            alert = result.scalar_one_or_none()
            
            if not alert:
                raise ValueError(f"Alert {alert_id} not found")
            
            # Validate action type
            valid_actions = ["email", "meeting", "resource_suggestion", "dismiss"]
            if action_type not in valid_actions:
                raise ValueError(f"Invalid action type. Must be one of: {valid_actions}")
            
            # Update alert status
            if action_type == "dismiss":
                alert.status = "dismissed"
            else:
                alert.status = "actioned"
            
            alert.advisor_id = advisor_id
            alert.advisor_notes = notes
            alert.actioned_at = datetime.utcnow()
            
            # Create intervention record
            intervention = Intervention(
                alert_id=alert_id,
                intervention_type=action_type,
                description=notes,
                scheduled_at=scheduled_at
            )
            
            self.session.add(intervention)
            await self.session.commit()
            await self.session.refresh(intervention)
            
            logger.info(f"Advisor {advisor_id} took action '{action_type}' on alert {alert_id}")
            
            return intervention
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error taking action on alert {alert_id}: {e}", exc_info=True)
            raise
    
    async def assign_alert_to_advisor(
        self,
        alert_id: int,
        advisor_id: str
    ) -> AdvisorAlert:
        """
        Assign alert to specific advisor
        
        تعيين تنبيه لمرشد محدد
        
        Args:
            alert_id: Alert ID / معرف التنبيه
            advisor_id: Advisor user ID / معرف المرشد
        
        Returns:
            Updated AdvisorAlert object / كائن AdvisorAlert المحدث
        """
        try:
            stmt = select(AdvisorAlert).where(AdvisorAlert.id == alert_id)
            result = await self.session.execute(stmt)
            alert = result.scalar_one_or_none()
            
            if not alert:
                raise ValueError(f"Alert {alert_id} not found")
            
            alert.advisor_id = advisor_id
            await self.session.commit()
            await self.session.refresh(alert)
            
            logger.info(f"Assigned alert {alert_id} to advisor {advisor_id}")
            
            return alert
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error assigning alert {alert_id}: {e}", exc_info=True)
            raise
    
    async def get_alert_by_id(self, alert_id: int) -> Optional[AdvisorAlert]:
        """
        Get alert by ID
        
        الحصول على تنبيه بالمعرف
        
        Args:
            alert_id: Alert ID / معرف التنبيه
        
        Returns:
            AdvisorAlert if found, None otherwise / AdvisorAlert إذا تم العثور عليه، None خلاف ذلك
        """
        try:
            stmt = select(AdvisorAlert).where(AdvisorAlert.id == alert_id)
            stmt = stmt.options(
                selectinload(AdvisorAlert.student),
                selectinload(AdvisorAlert.advisor),
                selectinload(AdvisorAlert.interventions)
            )
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting alert {alert_id}: {e}", exc_info=True)
            return None
    
    async def get_student_alerts(
        self,
        student_id: str,
        status: Optional[str] = None
    ) -> List[AdvisorAlert]:
        """
        Get all alerts for a specific student
        
        الحصول على جميع التنبيهات لطالب محدد
        
        Args:
            student_id: Student user ID / معرف الطالب
            status: Optional status filter / مرشح الحالة الاختياري
        
        Returns:
            List of AdvisorAlert objects / قائمة كائنات AdvisorAlert
        """
        try:
            stmt = select(AdvisorAlert).where(AdvisorAlert.student_id == student_id)
            
            if status:
                stmt = stmt.where(AdvisorAlert.status == status)
            
            stmt = stmt.order_by(AdvisorAlert.created_at.desc())
            
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(f"Error getting alerts for student {student_id}: {e}", exc_info=True)
            return []
