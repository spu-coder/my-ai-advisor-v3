"""
LLM Service Module
==================
This module handles LLM interactions with pluggable providers (managed APIs or local Ollama),
caching, and fallback logic for reliability. Supports OpenAI and Ollama providers.

وحدة خدمة LLM
==============
هذه الوحدة تتعامل مع تفاعلات LLM مع مقدمي خدمات قابلين للتبديل (APIs مدعومة أو Ollama محلي)،
التخزين المؤقت، ومنطق الاحتياطي للاعتمادية. تدعم مقدمي OpenAI و Ollama.
"""

import json
import hashlib
import logging
from dataclasses import dataclass
import httpx
import os
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

from cache_manager import cache_manager
from services.service_interface import ServiceAdapter

# ------------------------------------------------------------
# Service Connection Settings
# إعدادات الاتصال بالخدمات
# ------------------------------------------------------------
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("OLLAMA_MODEL", "llama3:8b")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
LLM_CACHE_TTL = int(os.getenv("LLM_CACHE_TTL", "900"))
LLM_REQUEST_TIMEOUT = float(os.getenv("LLM_REQUEST_TIMEOUT", "90"))
INTENT_FALLBACK_THRESHOLD = float(os.getenv("INTENT_FALLBACK_THRESHOLD", "0.7"))
DEFAULT_FALLBACK_INTENT = os.getenv("DEFAULT_FALLBACK_INTENT", "query_rag")

logger = logging.getLogger("LLM_SERVICE")

# ------------------------------------------------------------
# Data Models
# نماذج البيانات
# ------------------------------------------------------------
class Query(BaseModel):
    question: str
    user_id: str

class LLMResponse(BaseModel):
    answer: str
    source: str
    intent: str


@dataclass
class IntentPrediction:
    intent: str
    confidence: float
    reason: Optional[str] = None

# ------------------------------------------------------------
# قاعدة الأسئلة الشائعة (لأغراض التوجيه السريع)
# ------------------------------------------------------------
FAQ_DATABASE = {
    "متى آخر يوم للحذف والإضافة؟": "آخر يوم هو 20 فبراير 2025.",
    "ما هي درجة النجاح في مادة 101؟": "درجة C أو 60%.",
}

class BaseLLMClient:
    provider: str = "unknown"

    async def generate(self, prompt: str) -> str:  # pragma: no cover - interface
        raise NotImplementedError


class OllamaClient(BaseLLMClient):
    provider = "ollama"

    async def generate(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=LLM_REQUEST_TIMEOUT) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": LLM_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "num_predict": 500,
                    },
                },
            )
            response.raise_for_status()
            result = response.json()
            return result.get("response", "لم أجد إجابة محددة.").strip()


class OpenAIClient(BaseLLMClient):
    provider = "openai"

    def __init__(self):
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not set.")

    async def generate(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": OPENAI_MODEL,
            "temperature": 0.7,
            "messages": [
                {"role": "system", "content": "You are a helpful academic advisor."},
                {"role": "user", "content": prompt},
            ],
        }
        async with httpx.AsyncClient(timeout=LLM_REQUEST_TIMEOUT) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError("OpenAI response missing choices.")
            return choices[0]["message"]["content"].strip()


def _build_client(provider: str) -> BaseLLMClient:
    if provider == "openai":
        try:
            return OpenAIClient()
        except Exception as exc:
            logger.warning("Failed to initialize OpenAI client: %s. Falling back to Ollama.", exc)
            return OllamaClient()
    return OllamaClient()


class LLMClientFactory:
    def __init__(self):
        self.primary = _build_client(LLM_PROVIDER)
        self.fallback = None
        if self.primary.provider != "ollama":
            self.fallback = OllamaClient()

    async def generate(self, prompt: str) -> str:
        try:
            return await self.primary.generate(prompt)
        except Exception as exc:
            logger.error("Primary LLM provider '%s' failed: %s", self.primary.provider, exc)
            if self.fallback:
                return await self.fallback.generate(prompt)
            raise


_client_factory = LLMClientFactory()


def _hash_key(namespace: str, payload: str) -> str:
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{namespace}:{digest}"


async def generate_llm_response(prompt: str) -> str:
    cache_key = _hash_key("llm:response", prompt)
    cached = cache_manager.get(cache_key)
    if cached:
        return cached
    answer = await _client_factory.generate(prompt)
    cache_manager.set(cache_key, answer, ttl_seconds=LLM_CACHE_TTL)
    return answer

INTENT_KEYWORDS = {
    "analyze_progress": [
        "معدل",
        "gpa",
        "علامتي",
        "التقدم",
        "الساعات",
        "remaining",
    ],
    "simulate_gpa": [
        "محاكاة",
        "توقع",
        "expected gpa",
        "احسب معدلي",
    ],
    "graph_query": [
        "مهارات",
        "skills",
        "مسار",
        "path",
        "تخصص",
        "ترابط",
    ],
    "query_rag": [
        "لائحة",
        "نظام",
        "قانون",
        "خطة",
        "مقرر",
        "course description",
        "لوائح",
    ],
}


def _format_history_for_prompt(chat_history: Optional[List[Dict[str, Any]]]) -> str:
    if not chat_history:
        return ""
    lines = []
    for entry in chat_history[-6:]:
        role = entry.get("role", "user")
        role_label = "المستخدم" if role == "user" else "المساعد"
        content = entry.get("content", "")
        lines.append(f"{role_label}: {content}")
    return "\n".join(lines)


async def determine_intent(question: str) -> IntentPrediction:
    """
    Determine user intent using LLM-based classification.
    / تحديد نية المستخدم باستخدام تصنيف قائم على LLM.
    
    This function uses an LLM to classify the user's question into one of the
    following intents:
    - query_rag: Questions about regulations, study plans, course descriptions
    - analyze_progress: Questions about student records, GPA, remaining courses
    - simulate_gpa: Questions involving GPA simulation
    - graph_query: Questions about skills, specializations, course relationships
    - general_chat: General questions, greetings, or other queries
    
    تستخدم هذه الدالة LLM لتصنيف سؤال المستخدم إلى إحدى النوايا التالية:
    - query_rag: أسئلة حول اللوائح، الخطط الدراسية، توصيف المقررات
    - analyze_progress: أسئلة حول سجل الطالب، المعدل التراكمي، المقررات المتبقية
    - simulate_gpa: أسئلة تتضمن محاكاة المعدل التراكمي
    - graph_query: أسئلة حول المهارات، التخصصات، علاقات المقررات
    - general_chat: أسئلة عامة، تحيات، أو استفسارات أخرى
    
    Args:
        question: User's question / سؤال المستخدم
        
    Returns:
        Detected intent as string / النية المكتشفة كسلسلة نصية
        
    Example:
        >>> intent = await determine_intent("ما هو معدلي التراكمي؟")
        >>> print(intent)  # "analyze_progress"
    """
    
    # قائمة الأدوات المتاحة للـ Agent
    tools_description = """
    - query_rag: للأسئلة المتعلقة باللوائح، الخطط الدراسية، توصيف المقررات، أو أي معلومات موجودة في المستندات الرسمية.
    - analyze_progress: للأسئلة المتعلقة بسجل الطالب، المعدل التراكمي، المقررات المتبقية، أو المقررات القابلة للتسجيل.
    - simulate_gpa: للأسئلة التي تتضمن محاكاة المعدل التراكمي أو حساب المعدل المتوقع.
    - graph_query: للأسئلة المتعلقة بالمهارات، التخصصات، أو العلاقات بين المقررات (مثل: ما هي المهارات التي أكتسبها من مقرر X؟).
    - general_chat: للأسئلة العامة، التحية، أو أي سؤال لا يندرج تحت الفئات السابقة.
    """
    
    lowered = question.lower()
    for intent_name, keywords in INTENT_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return IntentPrediction(intent=intent_name, confidence=0.95, reason="Keyword heuristic")
    
    prompt = f"""
    أنت نظام توجيه ذكي. حلّل سؤال المستخدم واختر النية الأنسب من القائمة التالية:
    {tools_description}

    أعِد النتيجة بصيغة JSON فقط ودون أي نص إضافي:
    {{
        "intent": "analyze_progress",
        "confidence": 0.82,
        "reason": "لأنه يذكر المعدل التراكمي والدرجات."
    }}

    السؤال: "{question}"
    """
    
    raw_response = await generate_llm_response(prompt)
    valid_intents = {"query_rag", "analyze_progress", "simulate_gpa", "graph_query", "general_chat"}
    
    try:
        parsed = json.loads(raw_response)
        intent = str(parsed.get("intent", "")).strip().lower().replace('.', '').replace(' ', '_')
        confidence = float(parsed.get("confidence", 0.6))
        reason = parsed.get("reason")
    except Exception:
        intent = raw_response.strip().lower().replace('.', '').replace(' ', '_')
        confidence = 0.6
        reason = None
    
    if intent not in valid_intents:
        intent = "general_chat"
        confidence = min(confidence, 0.5)
    confidence = max(0.0, min(confidence, 1.0))
    return IntentPrediction(intent=intent, confidence=confidence, reason=reason)

async def process_agentic_query(
    question: str,
    user_id: Optional[str],
    service_adapter: Any,  # ServiceAdapter instance
    is_demo: bool = False,
    chat_history: Optional[List[Dict[str, Any]]] = None,
) -> LLMResponse:
    """
    Main Agentic RAG logic that routes questions to appropriate services.
    / المنطق الرئيسي لـ Agentic RAG الذي يوجه السؤال إلى الخدمة المناسبة.
    
    This function implements the core Agentic RAG pattern:
    1. Checks FAQ database for quick answers
    2. Determines user intent using LLM
    3. Routes to appropriate service based on intent
    4. Generates contextual answer with sources
    
    هذه الدالة تطبق نمط Agentic RAG الأساسي:
    1. التحقق من قاعدة الأسئلة الشائعة للإجابات السريعة
    2. تحديد نية المستخدم باستخدام LLM
    3. توجيه إلى الخدمة المناسبة بناءً على النية
    4. توليد إجابة سياقية مع المصادر
    
    Args:
        question: User's question / سؤال المستخدم
        user_id: User identifier (None for demo mode) / معرف المستخدم (None للوضع التجريبي)
        service_adapter: ServiceAdapter instance providing service interfaces / مثيل ServiceAdapter الذي يوفر واجهات الخدمات
        is_demo: Whether running in demo mode / هل يعمل في الوضع التجريبي
        
    Returns:
        LLMResponse object with answer, source, and intent
        / كائن LLMResponse يحتوي على الإجابة والمصدر والنية
        
    Example:
        >>> services = {
        ...     "documents": documents_service,
        ...     "progress": progress_service,
        ...     "graph": graph_service
        ... }
        >>> response = await process_agentic_query(
        ...     "ما هي متطلبات التخرج؟",
        ...     "student_001",
        ...     services
        ... )
        >>> print(response.answer)
    """
    
    # 1. فحص الأسئلة الشائعة (FAQ)
    if question in FAQ_DATABASE:
        return LLMResponse(answer=FAQ_DATABASE[question], source="FAQ Database", intent="query_rag")
    
    # 2. تحديد النية
    intent_prediction = await determine_intent(question)
    intent = intent_prediction.intent
    confidence = intent_prediction.confidence
    fallback_triggered = False
    if confidence < INTENT_FALLBACK_THRESHOLD:
        logger.warning(
            "Intent classification confidence %.2f below threshold %.2f. Falling back to %s.",
            confidence,
            INTENT_FALLBACK_THRESHOLD,
            DEFAULT_FALLBACK_INTENT,
        )
        intent = DEFAULT_FALLBACK_INTENT
        fallback_triggered = True

    history_block = _format_history_for_prompt(chat_history)
    history_section = f"""
السياق السابق:
{history_block}
---
""" if history_block else ""
    
    # 3. توجيه السؤال بناءً على النية
    
    # 3.1. استعلام RAG (المستندات)
    if intent == "query_rag":
        context_str, source_info = service_adapter.retrieve_context(question)
        
        if context_str:
            rag_prompt = f"""
            أنت "مرشدي الأكاديمي الذكي".
            أجب على السؤال بدقة بناءً على المستندات التالية فقط.
            إذا لم تجد الجواب، قل "لا أعرف".

            {history_section}
            المستندات:
            {context_str}

            السؤال:
            {question}
            """
            answer = await generate_llm_response(rag_prompt)
            source = source_info if not fallback_triggered else f"{source_info} (Fallback)"
            return LLMResponse(answer=answer, source=source, intent=intent)
        else:
            # إذا لم يتم العثور على سياق RAG، ننتقل إلى الدردشة العامة
            intent = "general_chat"

    # 3.2. تحليل التقدم (Progress Analysis)
    elif intent == "analyze_progress":
        # إذا كان الوضع التجريبي، لا يمكن الوصول للبيانات الشخصية
        if is_demo or not user_id:
            return LLMResponse(
                answer="⚠️ الوضع التجريبي لا يدعم الوصول إلى بياناتك الشخصية. يرجى تسجيل الدخول بالبيانات الصحيحة للوصول إلى هذه الميزة.",
                source="Demo Mode",
                intent=intent
            )
        
        try:
            # استخدام ServiceAdapter للوصول إلى خدمة التقدم (بدون الوصول المباشر لقاعدة البيانات)
            progress_data = await service_adapter.analyze_progress(user_id)
            
            # صياغة السؤال لـ LLM ليقوم بتحليل البيانات
            analysis_prompt = f"""
            أنت مرشد أكاديمي. بناءً على بيانات تقدم الطالب التالية، أجب على سؤاله مع الأخذ بعين الاعتبار السياق السابق إن وجد.

            {history_section}
            
            بيانات الطالب:
            - المعدل التراكمي الحالي: {progress_data['current_gpa']}
            - الساعات المكتملة: {progress_data['completed_hours']}
            - المقررات المتبقية: {progress_data['remaining_courses_count']}
            - المقررات القابلة للتسجيل: {', '.join([c['code'] for c in progress_data['registerable_next_semester']])}
            - المقررات المكتملة: {progress_data['completed_courses']}
            
            السؤال:
            {question}
            """
            answer = await generate_llm_response(analysis_prompt)
            return LLMResponse(answer=answer, source="Student Progress Service", intent=intent)
        except Exception as e:
            return LLMResponse(answer=f"حدث خطأ أثناء تحليل تقدم الطالب: {repr(e)}", source="Error", intent=intent)

    # 3.3. استعلام الرسم البياني (Graph Query)
    elif intent == "graph_query":
        # هنا يمكن استخدام LLM لتوليد استعلام Cypher أو استدعاء وظائف محددة في graph_service
        # لتبسيط الأمر، سنطلب من LLM الإجابة بناءً على البيانات المتاحة في graph_service
        
        # مثال: إذا كان السؤال عن مهارات مقرر معين
        if "مهارات" in question and "مقرر" in question:
            # نحتاج إلى استخراج اسم المقرر من السؤال
            # (هذه خطوة متقدمة تتطلب LLM أكثر ذكاءً أو استخدام مكتبة مثل LangChain Tooling)
            # لتبسيط الأمر، سنفترض أن المستخدم يسأل عن مهارات مقرر CS101
            skills = service_adapter.get_skills_for_course("CS101")
            if skills:
                answer = f"المقرر CS101 يدرس المهارات التالية: {', '.join(skills)}"
                return LLMResponse(answer=answer, source="Graph DB (Neo4j)", intent=intent)
        
        # إذا لم يتمكن من معالجة السؤال كاستعلام رسم بياني محدد، ننتقل إلى الدردشة العامة
        intent = "general_chat"
        
    # 3.4. محاكاة المعدل (GPA Simulation) - هذه الوظيفة يجب أن تستدعى مباشرة من الواجهة الأمامية
    # لأنها تتطلب مدخلات منظمة (درجات متوقعة)، لذا لن يتم توجيهها عبر Agent هنا.
    
    # 3.5. الدردشة العامة (General Chat)
    if intent == "general_chat":
        general_prompt = f"""
        أنت "مرشدي الأكاديمي الذكي". استخدم سياق المحادثة السابقة إن وجد لتقديم إجابة دقيقة ومفيدة.

        {history_section}
        السؤال:
        {question}
        """
        answer = await generate_llm_response(general_prompt)
        return LLMResponse(answer=answer, source="LLM (General)", intent=intent)
        
    # 4. حالة غير متوقعة
    return LLMResponse(answer="عذراً، لم أتمكن من فهم نيتك أو توجيه سؤالك إلى الخدمة المناسبة.", source="Agent Error", intent="unknown")

# تم حذف process_chat_request - يتم استخدام process_agentic_query مباشرة من main.py
