"""
Wellness Monitoring Service
==========================
Ethical digital phenotyping for student wellness

التنميط الظاهري الرقمي الأخلاقي لعافية الطالب
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database import WellnessMetric, WellnessAlert, User

logger = logging.getLogger("WELLNESS_MONITOR")


class WellnessMonitor:
    """
    Monitors student behavioral patterns (with consent)
    مراقبة الأنماط السلوكية للطالب (بموافقته)
    
    This service implements ethical digital phenotyping to detect early signs
    of academic stress, burnout, or wellness issues.
    
    تطبق هذه الخدمة التنميط الظاهري الرقمي الأخلاقي للكشف المبكر عن علامات
    الإجهاد الأكاديمي أو الإرهاق أو مشاكل العافية.
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize Wellness Monitor
        
        تهيئة مراقب العافية
        
        Args:
            session: Database session / جلسة قاعدة البيانات
        """
        self.session = session
        self.alert_thresholds = {
            "submission_pattern_change": 0.5,  # 50% deviation
            "session_duration_drop": 0.3,
            "social_withdrawal": 0.7,
            "late_night_activity_spike": 0.6
        }
    
    async def analyze_wellness(
        self,
        student_id: str,
        days_window: int = 14
    ) -> Dict[str, Any]:
        """
        Analyze student wellness indicators
        
        تحليل مؤشرات عافية الطالب
        
        Args:
            student_id: Student user ID / معرف الطالب
            days_window: Number of days to analyze / عدد الأيام للتحليل
        
        Returns:
            Dictionary containing:
            / قاموس يحتوي على:
            - wellness_score: 0-1 (1 = healthy, 0 = critical)
            - indicators: Behavioral indicators / المؤشرات السلوكية
            - deviations: List of detected deviations / قائمة الانحرافات المكتشفة
            - alert_level: "green" | "yellow" | "red"
            - recommended_intervention: Intervention recommendation / توصية التدخل
        """
        try:
            # Check if student has opted in
            opt_in = await self._check_opt_in(student_id)
            if not opt_in:
                return {
                    "wellness_score": None,
                    "message": "Student has not opted in to wellness monitoring / الطالب لم يوافق على مراقبة العافية",
                    "opt_in_required": True
                }
            
            # Get student's behavioral baseline
            baseline = await self._get_behavioral_baseline(student_id)
            
            # Get recent metrics (last N days)
            recent_metrics = await self._get_recent_metrics(student_id, days_window)
            
            # Calculate deviations
            deviations = self._calculate_deviations(baseline, recent_metrics)
            
            # Calculate wellness score
            wellness_score = self._calculate_wellness_score(deviations)
            
            # Determine alert level
            alert_level = self._determine_alert_level(wellness_score, deviations)
            
            # Generate recommendation
            recommendation = self._generate_intervention_recommendation(
                alert_level,
                deviations
            )
            
            # Create or update wellness alert if needed
            if alert_level in ["yellow", "red"]:
                await self._create_or_update_wellness_alert(
                    student_id=student_id,
                    alert_level=alert_level,
                    wellness_score=wellness_score,
                    deviations=deviations,
                    recommendation=recommendation
                )
            
            # Log metrics
            await self._log_wellness_metrics(student_id, recent_metrics, baseline)
            
            return {
                "wellness_score": wellness_score,
                "indicators": {
                    "submission_pattern": recent_metrics.get("submission_pattern"),
                    "session_duration_avg": recent_metrics.get("session_duration"),
                    "social_engagement": recent_metrics.get("forum_posts_count"),
                    "late_night_activity": recent_metrics.get("late_sessions_count")
                },
                "deviations": deviations,
                "alert_level": alert_level,
                "recommended_intervention": recommendation,
                "baseline": baseline,
                "recent_metrics": recent_metrics
            }
            
        except Exception as e:
            logger.error(f"Error analyzing wellness for student {student_id}: {e}", exc_info=True)
            return {
                "wellness_score": None,
                "error": str(e)
            }
    
    async def _check_opt_in(self, student_id: str) -> bool:
        """
        Check if student has opted in to wellness monitoring
        
        التحقق من موافقة الطالب على مراقبة العافية
        
        Args:
            student_id: Student user ID / معرف الطالب
        
        Returns:
            True if opted in, False otherwise / True إذا وافق، False خلاف ذلك
        """
        try:
            # Check most recent wellness alert for opt-in status
            stmt = select(WellnessAlert).where(
                WellnessAlert.student_id == student_id
            ).order_by(WellnessAlert.created_at.desc()).limit(1)
            
            result = await self.session.execute(stmt)
            alert = result.scalar_one_or_none()
            
            if alert:
                return alert.opt_in_status
            
            # Default to True if no previous record (assume consent)
            return True
            
        except Exception as e:
            logger.warning(f"Error checking opt-in for {student_id}: {e}")
            return True  # Default to opted in
    
    async def _get_behavioral_baseline(self, student_id: str) -> Dict[str, Any]:
        """
        Get student's normal behavioral pattern (baseline)
        
        الحصول على النمط السلوكي الطبيعي للطالب (المستوى الطبيعي)
        
        Calculated from first 30-60 days of activity
        محسوب من أول 30-60 يوم من النشاط
        
        Args:
            student_id: Student user ID / معرف الطالب
        
        Returns:
            Dictionary with baseline metrics / قاموس يحتوي على مقاييس المستوى الطبيعي
        """
        try:
            # Get metrics from first 60 days (or all if less than 60 days)
            cutoff_date = datetime.utcnow() - timedelta(days=60)
            
            stmt = select(WellnessMetric).where(
                and_(
                    WellnessMetric.student_id == student_id,
                    WellnessMetric.recorded_at >= cutoff_date
                )
            ).order_by(WellnessMetric.recorded_at.asc())
            
            result = await self.session.execute(stmt)
            metrics = result.scalars().all()
            
            if not metrics:
                # No baseline yet - return default values
                return {
                    "submission_timing": 2.0,  # Average days before deadline
                    "session_duration": 60.0,  # Average minutes per session
                    "forum_posts_per_week": 2.0,
                    "late_sessions_per_week": 1.0,
                    "baseline_established": False
                }
            
            # Calculate averages for each metric type
            baseline = {
                "submission_timing": 2.0,
                "session_duration": 60.0,
                "forum_posts_per_week": 2.0,
                "late_sessions_per_week": 1.0,
                "baseline_established": True
            }
            
            # Group metrics by type and calculate averages
            metric_groups = {}
            for metric in metrics:
                if metric.metric_type not in metric_groups:
                    metric_groups[metric.metric_type] = []
                metric_groups[metric.metric_type].append(metric.metric_value)
            
            # Calculate averages
            for metric_type, values in metric_groups.items():
                if values:
                    avg_value = sum(values) / len(values)
                    
                    if metric_type == "submission_timing":
                        baseline["submission_timing"] = avg_value
                    elif metric_type == "session_duration":
                        baseline["session_duration"] = avg_value
                    elif metric_type == "forum_posts":
                        baseline["forum_posts_per_week"] = avg_value
                    elif metric_type == "late_sessions":
                        baseline["late_sessions_per_week"] = avg_value
            
            return baseline
            
        except Exception as e:
            logger.error(f"Error getting baseline for {student_id}: {e}", exc_info=True)
            return {
                "submission_timing": 2.0,
                "session_duration": 60.0,
                "forum_posts_per_week": 2.0,
                "late_sessions_per_week": 1.0,
                "baseline_established": False
            }
    
    async def _get_recent_metrics(
        self,
        student_id: str,
        days: int
    ) -> Dict[str, Any]:
        """
        Get recent behavioral metrics
        
        الحصول على المقاييس السلوكية الأخيرة
        
        Args:
            student_id: Student user ID / معرف الطالب
            days: Number of days to look back / عدد الأيام للرجوع
        
        Returns:
            Dictionary with recent metrics / قاموس يحتوي على المقاييس الأخيرة
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            stmt = select(WellnessMetric).where(
                and_(
                    WellnessMetric.student_id == student_id,
                    WellnessMetric.recorded_at >= cutoff_date
                )
            )
            
            result = await self.session.execute(stmt)
            metrics = result.scalars().all()
            
            if not metrics:
                return {
                    "submission_pattern": None,
                    "session_duration": None,
                    "forum_posts_count": 0,
                    "late_night_activity": 0
                }
            
            # Calculate recent averages
            recent = {
                "submission_pattern": None,
                "session_duration": None,
                "forum_posts_count": 0,
                "late_night_activity": 0
            }
            
            metric_groups = {}
            for metric in metrics:
                if metric.metric_type not in metric_groups:
                    metric_groups[metric.metric_type] = []
                metric_groups[metric.metric_type].append(metric.metric_value)
            
            # Calculate averages
            for metric_type, values in metric_groups.items():
                if values:
                    avg_value = sum(values) / len(values)
                    
                    if metric_type == "submission_timing":
                        recent["submission_pattern"] = avg_value
                    elif metric_type == "session_duration":
                        recent["session_duration"] = avg_value
                    elif metric_type == "forum_posts":
                        recent["forum_posts_count"] = len(values)  # Count, not average
                    elif metric_type == "late_sessions":
                        recent["late_night_activity"] = len(values)  # Count
            
            return recent
            
        except Exception as e:
            logger.error(f"Error getting recent metrics for {student_id}: {e}", exc_info=True)
            return {
                "submission_pattern": None,
                "session_duration": None,
                "forum_posts_count": 0,
                "late_night_activity": 0
            }
    
    def _calculate_deviations(
        self,
        baseline: Dict[str, Any],
        recent: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Calculate deviations from baseline
        
        حساب الانحرافات عن المستوى الطبيعي
        
        Args:
            baseline: Baseline metrics / مقاييس المستوى الطبيعي
            recent: Recent metrics / المقاييس الأخيرة
        
        Returns:
            List of deviation dictionaries / قائمة قواميس الانحرافات
        """
        deviations = []
        
        # Submission pattern deviation
        if baseline.get("submission_timing") and recent.get("submission_pattern") is not None:
            baseline_val = baseline["submission_timing"]
            recent_val = recent["submission_pattern"]
            
            if baseline_val > 0:
                deviation_pct = abs(recent_val - baseline_val) / baseline_val
                
                if deviation_pct > self.alert_thresholds["submission_pattern_change"]:
                    deviations.append({
                        "type": "submission_pattern_change",
                        "deviation": deviation_pct,
                        "severity": "medium" if deviation_pct < 0.7 else "high",
                        "description": f"تغيير في نمط التسليم بنسبة {deviation_pct*100:.1f}%",
                        "baseline": baseline_val,
                        "current": recent_val
                    })
        
        # Session duration deviation
        if baseline.get("session_duration") and recent.get("session_duration") is not None:
            baseline_val = baseline["session_duration"]
            recent_val = recent["session_duration"]
            
            if baseline_val > 0:
                deviation_pct = abs(recent_val - baseline_val) / baseline_val
                
                if deviation_pct > self.alert_thresholds["session_duration_drop"]:
                    if recent_val < baseline_val:  # Only alert on decrease
                        deviations.append({
                            "type": "session_duration_drop",
                            "deviation": deviation_pct,
                            "severity": "medium" if deviation_pct < 0.5 else "high",
                            "description": f"انخفاض مدة الجلسات بنسبة {deviation_pct*100:.1f}%",
                            "baseline": baseline_val,
                            "current": recent_val
                        })
        
        # Social withdrawal detection
        if baseline.get("forum_posts_per_week") is not None and recent.get("forum_posts_count") is not None:
            baseline_val = baseline["forum_posts_per_week"]
            recent_val = recent["forum_posts_count"] / 2.0  # Approximate per week
            
            if baseline_val > 0:
                deviation_pct = abs(recent_val - baseline_val) / baseline_val
                
                if recent_val < baseline_val and deviation_pct > self.alert_thresholds["social_withdrawal"]:
                    deviations.append({
                        "type": "social_withdrawal",
                        "deviation": deviation_pct,
                        "severity": "high",
                        "description": f"انخفاض المشاركة الاجتماعية بنسبة {deviation_pct*100:.1f}%",
                        "baseline": baseline_val,
                        "current": recent_val
                    })
        
        # Late-night activity spike
        if baseline.get("late_sessions_per_week") is not None and recent.get("late_night_activity") is not None:
            baseline_val = baseline["late_sessions_per_week"]
            recent_val = recent["late_night_activity"] / 2.0  # Approximate per week
            
            if baseline_val > 0:
                deviation_pct = abs(recent_val - baseline_val) / baseline_val
                
                if recent_val > baseline_val and deviation_pct > self.alert_thresholds["late_night_activity_spike"]:
                    deviations.append({
                        "type": "late_night_activity_spike",
                        "deviation": deviation_pct,
                        "severity": "medium",
                        "description": f"زيادة النشاط الليلي بنسبة {deviation_pct*100:.1f}%",
                        "baseline": baseline_val,
                        "current": recent_val
                    })
        
        return deviations
    
    def _calculate_wellness_score(self, deviations: List[Dict[str, Any]]) -> float:
        """
        Calculate overall wellness score (0-1)
        
        حساب مؤشر العافية الشامل (0-1)
        
        Args:
            deviations: List of deviations / قائمة الانحرافات
        
        Returns:
            Wellness score between 0 and 1 / مؤشر العافية بين 0 و 1
        """
        if not deviations:
            return 1.0  # Perfect wellness
        
        # Weight deviations by severity
        severity_weights = {"low": 0.1, "medium": 0.3, "high": 0.5}
        
        total_impact = sum(
            severity_weights.get(d.get("severity", "medium"), 0.3)
            for d in deviations
        )
        
        # Score decreases with more/severe deviations
        score = max(0.0, 1.0 - (total_impact / 2))
        
        return score
    
    def _determine_alert_level(
        self,
        wellness_score: float,
        deviations: List[Dict[str, Any]]
    ) -> str:
        """
        Determine alert level: green, yellow, red
        
        تحديد مستوى التنبيه: أخضر، أصفر، أحمر
        
        Args:
            wellness_score: Overall wellness score / مؤشر العافية الشامل
            deviations: List of deviations / قائمة الانحرافات
        
        Returns:
            Alert level string / سلسلة مستوى التنبيه
        """
        if wellness_score > 0.7:
            return "green"
        elif wellness_score > 0.4:
            return "yellow"
        else:
            return "red"
    
    def _generate_intervention_recommendation(
        self,
        alert_level: str,
        deviations: List[Dict[str, Any]]
    ) -> str:
        """
        Generate intervention recommendation
        
        توليد توصية للتدخل
        
        Based on Table 2 in reference document
        بناءً على الجدول 2 في المستند المرجعي
        
        Args:
            alert_level: Alert level / مستوى التنبيه
            deviations: List of deviations / قائمة الانحرافات
        
        Returns:
            Recommendation string / سلسلة التوصية
        """
        if alert_level == "green":
            return "لا حاجة للتدخل. استمرار المراقبة."
        
        elif alert_level == "yellow":
            # Level 1-2 interventions
            recommendations = []
            
            for dev in deviations:
                if dev["type"] == "submission_pattern_change":
                    recommendations.append(
                        "المستوى 1: إرسال نصائح تلقائية لإدارة الوقت"
                    )
                elif dev["type"] == "social_withdrawal":
                    recommendations.append(
                        "المستوى 2: اقتراح مجموعة دراسة أو اتصال مع الأقران"
                    )
                elif dev["type"] == "session_duration_drop":
                    recommendations.append(
                        "المستوى 1: تذكير بفوائد الجلسات المنتظمة"
                    )
                elif dev["type"] == "late_night_activity_spike":
                    recommendations.append(
                        "المستوى 1: نصائح حول أهمية النوم الكافي"
                    )
            
            if recommendations:
                return " | ".join(recommendations)
            else:
                return "المستوى 1: مراقبة إضافية مطلوبة"
        
        else:  # red
            # Level 3: Human intervention required
            return "المستوى 3: إحالة لمراجعة المرشد البشري. حالة عالية الخطورة محتملة."
    
    async def _create_or_update_wellness_alert(
        self,
        student_id: str,
        alert_level: str,
        wellness_score: float,
        deviations: List[Dict[str, Any]],
        recommendation: str
    ) -> WellnessAlert:
        """
        Create or update wellness alert
        
        إنشاء أو تحديث تنبيه العافية
        
        Args:
            student_id: Student user ID / معرف الطالب
            alert_level: Alert level / مستوى التنبيه
            wellness_score: Wellness score / مؤشر العافية
            deviations: List of deviations / قائمة الانحرافات
            recommendation: Intervention recommendation / توصية التدخل
        
        Returns:
            Created or updated WellnessAlert / تنبيه العافية المنشأ أو المحدث
        """
        try:
            # Check for existing active alert
            stmt = select(WellnessAlert).where(
                and_(
                    WellnessAlert.student_id == student_id,
                    WellnessAlert.alert_level == alert_level
                )
            ).order_by(WellnessAlert.created_at.desc()).limit(1)
            
            result = await self.session.execute(stmt)
            existing_alert = result.scalar_one_or_none()
            
            if existing_alert:
                # Update existing alert
                existing_alert.wellness_score = wellness_score
                existing_alert.indicators = [d["type"] for d in deviations]
                existing_alert.recommended_intervention = recommendation
                existing_alert.updated_at = datetime.utcnow()
                
                await self.session.commit()
                await self.session.refresh(existing_alert)
                
                logger.info(f"Updated wellness alert {existing_alert.id} for student {student_id}")
                return existing_alert
            else:
                # Create new alert
                alert = WellnessAlert(
                    student_id=student_id,
                    alert_level=alert_level,
                    indicators=[d["type"] for d in deviations],
                    wellness_score=wellness_score,
                    recommended_intervention=recommendation,
                    opt_in_status=True
                )
                
                self.session.add(alert)
                await self.session.commit()
                await self.session.refresh(alert)
                
                logger.info(f"Created wellness alert {alert.id} for student {student_id}")
                return alert
                
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating/updating wellness alert: {e}", exc_info=True)
            raise
    
    async def _log_wellness_metrics(
        self,
        student_id: str,
        recent_metrics: Dict[str, Any],
        baseline: Dict[str, Any]
    ) -> None:
        """
        Log wellness metrics for future baseline calculation
        
        تسجيل مقاييس العافية لحساب المستوى الطبيعي المستقبلي
        
        Args:
            student_id: Student user ID / معرف الطالب
            recent_metrics: Recent metrics / المقاييس الأخيرة
            baseline: Baseline metrics / مقاييس المستوى الطبيعي
        """
        try:
            now = datetime.utcnow()
            
            # Log each metric type
            if recent_metrics.get("submission_pattern") is not None:
                metric = WellnessMetric(
                    student_id=student_id,
                    metric_type="submission_timing",
                    metric_value=recent_metrics["submission_pattern"],
                    baseline_value=baseline.get("submission_timing"),
                    deviation_percentage=(
                        abs(recent_metrics["submission_pattern"] - baseline.get("submission_timing", 0)) / 
                        max(baseline.get("submission_timing", 1), 1) * 100
                        if baseline.get("submission_timing") else None
                    ),
                    recorded_at=now
                )
                self.session.add(metric)
            
            if recent_metrics.get("session_duration") is not None:
                metric = WellnessMetric(
                    student_id=student_id,
                    metric_type="session_duration",
                    metric_value=recent_metrics["session_duration"],
                    baseline_value=baseline.get("session_duration"),
                    deviation_percentage=(
                        abs(recent_metrics["session_duration"] - baseline.get("session_duration", 0)) / 
                        max(baseline.get("session_duration", 1), 1) * 100
                        if baseline.get("session_duration") else None
                    ),
                    recorded_at=now
                )
                self.session.add(metric)
            
            await self.session.commit()
            
        except Exception as e:
            await self.session.rollback()
            logger.warning(f"Error logging wellness metrics: {e}")
    
    async def get_wellness_alerts(
        self,
        alert_level: Optional[str] = None,
        limit: int = 50
    ) -> List[WellnessAlert]:
        """
        Get wellness alerts
        
        الحصول على تنبيهات العافية
        
        Args:
            alert_level: Optional filter by alert level / مرشح مستوى التنبيه الاختياري
            limit: Maximum number of alerts / الحد الأقصى لعدد التنبيهات
        
        Returns:
            List of WellnessAlert objects / قائمة كائنات WellnessAlert
        """
        try:
            stmt = select(WellnessAlert).where(WellnessAlert.opt_in_status == True)
            
            if alert_level:
                stmt = stmt.where(WellnessAlert.alert_level == alert_level)
            
            stmt = stmt.order_by(WellnessAlert.created_at.desc()).limit(limit)
            
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(f"Error getting wellness alerts: {e}", exc_info=True)
            return []
    
    async def get_student_wellness_history(
        self,
        student_id: str,
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get student wellness history
        
        الحصول على تاريخ عافية الطالب
        
        Args:
            student_id: Student user ID / معرف الطالب
            limit: Maximum number of records / الحد الأقصى لعدد السجلات
        
        Returns:
            List of wellness history dictionaries / قائمة قواميس تاريخ العافية
        """
        try:
            stmt = select(WellnessAlert).where(
                WellnessAlert.student_id == student_id
            ).order_by(WellnessAlert.created_at.desc()).limit(limit)
            
            result = await self.session.execute(stmt)
            alerts = result.scalars().all()
            
            return [
                {
                    "id": alert.id,
                    "alert_level": alert.alert_level,
                    "wellness_score": alert.wellness_score,
                    "indicators": alert.indicators,
                    "recommended_intervention": alert.recommended_intervention,
                    "created_at": alert.created_at.isoformat() if alert.created_at else None
                }
                for alert in alerts
            ]
            
        except Exception as e:
            logger.error(f"Error getting wellness history for {student_id}: {e}", exc_info=True)
            return []
