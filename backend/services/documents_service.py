"""
Documents Service Module
========================
This module handles document ingestion, processing, and RAG retrieval:
- Document loading and parsing (PDF, DOCX, images with OCR)
- Text chunking (parent-child split strategy)
- Embedding generation and storage in ChromaDB
- Context retrieval for RAG queries

وحدة خدمة المستندات
====================
هذه الوحدة تتعامل مع فهرسة ومعالجة واسترجاع المستندات:
- تحميل وتحليل المستندات (PDF, DOCX, صور مع OCR)
- تقسيم النص (استراتيجية تقسيم أب-ابن)
- توليد التضمينات وتخزينها في ChromaDB
- استرجاع السياق لاستعلامات RAG
"""

import os
import hashlib
import sys
import logging
import chromadb
import re
from typing import Dict, Any, Optional, List
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.documents import Document
from data_processor import ingest_all_documents
# استخدام الإصدارات المحدثة لتجنب تحذيرات deprecation
try:
    from langchain_chroma import Chroma
except ImportError:
    from langchain_community.vectorstores import Chroma

try:
    from langchain_ollama import OllamaEmbeddings
except ImportError:
    from langchain_community.embeddings import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from cache_manager import cache_manager

# ------------------------------------------------------------
# إعدادات الاتصال بالخدمات
# ------------------------------------------------------------
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://llm-service:11434")
CHROMA_HOST = os.getenv("CHROMA_HOST", "vector-db")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
PDF_DATA_DIR = "/app/data"
CACHE_TTL_SECONDS = int(os.getenv("RAG_CACHE_TTL", "600"))

logger = logging.getLogger("DOCUMENTS_SERVICE")

# ------------------------------------------------------------
# تهيئة مكونات RAG
# ------------------------------------------------------------
parent_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=200)
child_splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=50)

# إعداد OllamaEmbeddings
# ملاحظة: timeout يتم إعداده في httpx client داخلياً
embeddings = OllamaEmbeddings(
    base_url=OLLAMA_BASE_URL, 
    model="llama3:8b"
)

# إعداد الاتصال مع ChromaDB (v2 API)
# ملاحظة: ChromaDB v2 يستخدم طريقة مختلفة للاتصال
try:
    # استخدام ChromaDB v2 API - الاتصال المباشر بدون settings deprecated
    client = chromadb.HttpClient(
        host=CHROMA_HOST,
        port=CHROMA_PORT
    )
    logger.info(f"Connected to ChromaDB at {CHROMA_HOST}:{CHROMA_PORT}")
except Exception as e:
    logger.error(f"Failed to connect to ChromaDB: {e}")
    raise

# استخدام langchain_chroma مع client مباشرة
vectorstore = Chroma(
    collection_name="academic_docs_split",
    embedding_function=embeddings,
    client=client
)

# استخدام retriever بسيط من vectorstore
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

# ------------------------------------------------------------
# وظائف الخدمة
# ------------------------------------------------------------

def ingest_documents() -> Dict[str, Any]:
    """
    Index all supported documents in the data directory using multimodal processor.
    / فهرسة جميع المستندات المدعومة في مجلد البيانات باستخدام معالج البيانات المتعددة الوسائط.
    
    This function:
    1. Loads all supported documents (PDF, DOCX, images) from data directory
    2. Processes images with OCR if needed
    3. Splits documents into chunks using parent-child strategy
    4. Generates embeddings using Ollama
    5. Stores embeddings in ChromaDB vector store
    
    هذه الدالة:
    1. تحمّل جميع المستندات المدعومة (PDF, DOCX, صور) من مجلد البيانات
    2. تعالج الصور مع OCR إذا لزم الأمر
    3. تقسم المستندات إلى أجزاء باستخدام استراتيجية أب-ابن
    4. تولد التضمينات باستخدام Ollama
    5. تخزن التضمينات في مخزن المتجهات ChromaDB
    
    Returns:
        Dictionary with status and message:
        / قاموس يحتوي على الحالة والرسالة:
        - status: "success" or "error"
        - message: Descriptive message
        - documents_count: Number of documents processed
        - chunks_count: Number of chunks created
        
    Raises:
        Exception: If document processing fails
        
    Example:
        >>> result = ingest_documents()
        >>> print(result)
        {'status': 'success', 'message': 'Indexed 10 documents', ...}
    """
    try:
        logger.info(f"Starting document ingestion from {PDF_DATA_DIR}")
        
        # التحقق من وجود المجلد
        if not os.path.exists(PDF_DATA_DIR):
            logger.error(f"Data directory {PDF_DATA_DIR} does not exist")
            return {"status": "error", "message": f"Data directory {PDF_DATA_DIR} does not exist"}
        
        # تحميل المستندات
        logger.info("Loading documents...")
        loaded_docs = ingest_all_documents(PDF_DATA_DIR)
        
        if not loaded_docs:
            logger.warning(f"No supported documents found in {PDF_DATA_DIR}")
            return {"status": "error", "message": f"No supported documents found in {PDF_DATA_DIR}. Please add PDF, DOCX, or TXT files."}

        logger.info(f"Loaded {len(loaded_docs)} documents. Starting indexing...")
        
        # تقسيم المستندات إلى chunks قبل الإضافة
        logger.info("Splitting documents into chunks...")
        split_docs = []
        for doc in loaded_docs:
            # Enrich metadata before splitting
            enriched_metadata = _enrich_metadata(doc.page_content, doc.metadata)
            doc.metadata = enriched_metadata
            
            chunks = parent_splitter.split_documents([doc])
            split_docs.extend(chunks)
        
        logger.info(f"Split {len(loaded_docs)} documents into {len(split_docs)} chunks")

        # إضافة المستندات إلى RAG Retriever
        # يتم مسح المجموعة القديمة قبل الإضافة لضمان تحديث الفهرس
        try:
            # محاولة حذف المجموعة القديمة إذا كانت موجودة
            try:
                collection = client.get_collection("academic_docs_split")
                client.delete_collection("academic_docs_split")
                logger.info("Deleted old collection")
            except Exception as e:
                # المجموعة غير موجودة، هذا طبيعي
                logger.info(f"No existing collection to delete: {e}")
                pass
            
            # إنشاء vectorstore جديد مع المستندات
            # هذا قد يستغرق وقتاً طويلاً إذا كانت المستندات كبيرة
            logger.info(f"Creating embeddings for {len(loaded_docs)} documents... This may take a while...")
            
            # تقسيم المستندات إلى دفعات لتجنب timeout
            batch_size = 5  # تقليل حجم الدفعة لتجنب timeout
            global vectorstore, retriever
            
            # إنشاء vectorstore فارغ أولاً
            try:
                # محاولة الحصول على collection موجودة أو إنشاء واحدة جديدة
                try:
                    existing_collection = client.get_collection("academic_docs_split")
                    vectorstore = Chroma(
                        collection_name="academic_docs_split",
                        embedding_function=embeddings,
                        client=client
                    )
                except:
                    # إنشاء collection جديدة مع أول دفعة من chunks
                    logger.info(f"Creating new collection with first batch of {min(batch_size, len(split_docs))} chunks...")
                    vectorstore = Chroma.from_documents(
                        documents=split_docs[:batch_size] if len(split_docs) > batch_size else split_docs,
                        embedding=embeddings,
                        collection_name="academic_docs_split",
                        client=client
                    )
                    
                    # إضافة باقي chunks على دفعات
                    if len(split_docs) > batch_size:
                        total_batches = (len(split_docs) + batch_size - 1) // batch_size
                        for i in range(batch_size, len(split_docs), batch_size):
                            batch = split_docs[i:i+batch_size]
                            batch_num = i // batch_size + 1
                            logger.info(f"Adding batch {batch_num}/{total_batches} ({len(batch)} chunks)...")
                            try:
                                vectorstore.add_documents(batch)
                            except Exception as batch_error:
                                logger.error(f"Error adding batch {batch_num}: {batch_error}")
                                # محاولة مرة أخرى مع دفعة أصغر
                                for single_doc in batch:
                                    try:
                                        vectorstore.add_documents([single_doc])
                                    except Exception as single_error:
                                        logger.error(f"Error adding single document: {single_error}")
            except Exception as e:
                logger.error(f"Error creating vectorstore: {e}", exc_info=True)
                # محاولة طريقة بديلة - إنشاء مباشر مع chunks
                logger.info("Trying alternative method: creating vectorstore directly with all chunks...")
                try:
                    vectorstore = Chroma.from_documents(
                        documents=split_docs,
                        embedding=embeddings,
                        collection_name="academic_docs_split",
                        client=client
                    )
                except Exception as alt_error:
                    logger.error(f"Alternative method also failed: {alt_error}", exc_info=True)
                    raise
            
            retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
            
            # التحقق من أن vectorstore يحتوي على بيانات
            try:
                collection = client.get_collection("academic_docs_split")
                count = collection.count()
                logger.info(f"Vectorstore contains {count} chunks from {len(loaded_docs)} documents")
            except Exception as e:
                logger.warning(f"Could not verify vectorstore count: {e}")
            
            logger.info(f"Successfully ingested and indexed {len(loaded_docs)} documents ({len(split_docs)} chunks).")
            return {
                "status": "success", 
                "message": f"Successfully ingested and indexed {len(loaded_docs)} documents ({len(split_docs)} chunks)."
            }
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error during document ingestion: {error_msg}", exc_info=True)
            
            # رسائل خطأ أكثر وضوحاً
            if "timeout" in error_msg.lower() or "connection" in error_msg.lower():
                return {
                    "status": "error", 
                    "message": f"Connection timeout. Please check if Ollama is running and try again. Error: {error_msg[:100]}"
                }
            elif "chroma" in error_msg.lower() or "chromadb" in error_msg.lower():
                return {
                    "status": "error", 
                    "message": f"ChromaDB error. Please check if ChromaDB is running. Error: {error_msg[:100]}"
                }
            else:
                return {
                    "status": "error", 
                    "message": f"Error ingesting documents: {error_msg[:200]}"
                }
    except Exception as e:
        logger.error(f"Unexpected error in ingest_documents: {e}", exc_info=True)
        return {"status": "error", "message": f"Unexpected error: {str(e)[:200]}"}

def _cache_key(question: str) -> str:
    digest = hashlib.sha256(question.encode("utf-8")).hexdigest()
    return f"rag:context:{digest}"


def retrieve_context(question: str) -> tuple[Optional[str], str]:
    """
    Retrieve relevant context from vector store for RAG queries.
    / استرجاع السياق ذي الصلة من مخزن المتجهات لاستعلامات RAG.
    
    This function performs semantic search in ChromaDB to find the most
    relevant document chunks for the given question.
    
    هذه الدالة تقوم بالبحث الدلالي في ChromaDB للعثور على أجزاء
    المستندات الأكثر صلة بالسؤال المحدد.
    
    Args:
        question: User's question for context retrieval
        / سؤال المستخدم لاسترجاع السياق
        
    Returns:
        Tuple of (context_string, source_info):
        / مجموعة من (سلسلة_السياق، معلومات_المصدر):
        - context_string: Concatenated relevant chunks
        - source_info: Information about source documents
        
    Example:
        >>> context, source = retrieve_context("ما هي متطلبات التخرج؟")
        >>> print(context[:100])  # First 100 characters
    """
    try:
        cache_key = _cache_key(question)
        cached = cache_manager.get(cache_key)
        if cached:
            return cached.get("context"), cached.get("source")

        logger.info(f"Retrieving context for question: {question[:100]}")
        retrieved_docs = retriever.invoke(question)
        
        if not retrieved_docs:
            logger.warning("No documents retrieved from vectorstore")
            return None, "LLM (No RAG)"
        
        logger.info(f"Retrieved {len(retrieved_docs)} documents")
        source_info = ", ".join(list(set([doc.metadata.get("source", "Unknown") for doc in retrieved_docs])))
        context_str = "\n\n---\n\n".join([doc.page_content for doc in retrieved_docs])
        
        logger.info(f"Context length: {len(context_str)} characters from sources: {source_info}")
        response_payload = {"context": context_str, "source": f"RAG ({source_info})"}
        cache_manager.set(cache_key, response_payload, ttl_seconds=CACHE_TTL_SECONDS)
        return response_payload["context"], response_payload["source"]
    except Exception as e:
        logger.error(f"Error retrieving context: {e}", exc_info=True)
        return None, "LLM (RAG Error)"

def get_rag_retriever():
    """إرجاع كائن RAG Retriever للاستخدام المباشر في Agent."""
    return retriever

# ------------------------------------------------------------
# Context-Aware Metadata Enhancement Functions
# دوال تحسين البيانات الوصفية الموجهة بالسياق
# ------------------------------------------------------------

def _enrich_metadata(content: str, original_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enrich metadata with comprehensive fields for context-aware filtering
    
    إثراء البيانات الوصفية بحقول شاملة للتصفية الموجهة بالسياق
    
    Args:
        content: Document content / محتوى المستند
        original_metadata: Original metadata dictionary / قاموس البيانات الوصفية الأصلي
    
    Returns:
        Enriched metadata dictionary / قاموس البيانات الوصفية المثراة
    """
    enriched = {
        **original_metadata,
        
        # Versioning (حسب الرؤية الأصلية)
        "plan_version": _extract_plan_version(content),
        "applies_to_cohorts": _extract_cohorts(content),
        "status": "active",  # active, deprecated, archived
        
        # Document classification
        "doc_category": _classify_document(content, original_metadata.get("source", "")),
        
        # Timestamp
        "created_at": datetime.utcnow().isoformat(),
        
        # Quality score (simplified)
        "quality_score": _calculate_quality_score(content),
    }
    
    return enriched

def _extract_plan_version(content: str) -> str:
    """
    Extract plan version from content
    
    استخراج إصدار الخطة من المحتوى
    
    Args:
        content: Document content / محتوى المستند
    
    Returns:
        Plan version year (e.g., "2024") or "unknown" / سنة إصدار الخطة أو "unknown"
    """
    # Look for "خطة 2024" or "Plan 2024" or "2024 plan"
    patterns = [
        r'(?:خطة|plan|الخطة)\s*(\d{4})',
        r'(\d{4})\s*(?:plan|خطة)',
        r'خطة\s*الدراسية\s*(\d{4})',
        r'الخطة\s*الدراسية\s*(\d{4})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            year = match.group(1)
            # Validate year (reasonable range)
            if 2015 <= int(year) <= 2030:
                return year
    
    return "unknown"

def _extract_cohorts(content: str) -> List[str]:
    """
    Extract applicable cohorts from content
    
    استخراج الأفواج المنطبقة من المحتوى
    
    Args:
        content: Document content / محتوى المستند
    
    Returns:
        List of cohort identifiers / قائمة معرفات الأفواج
    """
    cohorts = []
    
    # Look for cohort patterns like "2018-2021", "2022+", "cohort 2022"
    patterns = [
        r'(\d{4})\s*[-–]\s*(\d{4})',  # 2018-2021
        r'(\d{4})\+',  # 2022+
        r'cohort\s*(\d{4})',
        r'دفعة\s*(\d{4})',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                if len(match) == 2:
                    cohorts.append(f"{match[0]}-{match[1]}")
                else:
                    cohorts.append(match[0])
            else:
                cohorts.append(match)
    
    # If no specific cohorts found, try to infer from plan version
    plan_version = _extract_plan_version(content)
    if plan_version != "unknown":
        # Assume applies to students enrolled in that year and later
        cohorts.append(f"{plan_version}+")
    
    return list(set(cohorts)) if cohorts else ["all"]

def _classify_document(content: str, source: str) -> str:
    """
    Classify document type
    
    تصنيف نوع المستند
    
    Args:
        content: Document content / محتوى المستند
        source: Source file path / مسار الملف المصدر
    
    Returns:
        Document category / فئة المستند
    """
    content_lower = content.lower()
    source_lower = source.lower()
    
    # Classification keywords
    categories = {
        "regulation": ["لائحة", "قرار", "regulation", "policy", "قواعد", "نظام"],
        "syllabus": ["مقرر", "syllabus", "course", "وصف المقرر", "course description"],
        "handbook": ["دليل", "handbook", "guide", "manual", "كتيب"],
        "calendar": ["تقويم", "calendar", "جدول", "schedule", "مواعيد"],
        "exam": ["امتحان", "exam", "اختبار", "test", "examination"],
        "announcement": ["إعلان", "announcement", "notice", "تنبيه"],
    }
    
    # Check content
    for category, keywords in categories.items():
        if any(keyword in content_lower for keyword in keywords):
            return category
    
    # Check source filename
    for category, keywords in categories.items():
        if any(keyword in source_lower for keyword in keywords):
            return category
    
    return "general"

def _calculate_quality_score(content: str) -> float:
    """
    Calculate document quality score (0-1)
    
    حساب درجة جودة المستند (0-1)
    
    Args:
        content: Document content / محتوى المستند
    
    Returns:
        Quality score between 0 and 1 / درجة الجودة بين 0 و 1
    """
    if not content or len(content.strip()) == 0:
        return 0.0
    
    score = 1.0
    
    # Penalize very short documents
    if len(content) < 100:
        score -= 0.3
    
    # Penalize very long documents (might be noise)
    if len(content) > 100000:
        score -= 0.2
    
    # Check for structure (headers, lists, etc.)
    has_structure = bool(
        re.search(r'#+\s+\w+|^\d+\.|^[•\-\*]', content, re.MULTILINE)
    )
    if not has_structure:
        score -= 0.1
    
    # Check for Arabic/English content (both is good)
    has_arabic = bool(re.search(r'[\u0600-\u06FF]', content))
    has_english = bool(re.search(r'[a-zA-Z]', content))
    
    if has_arabic and has_english:
        score += 0.1  # Bonus for bilingual
    
    return max(0.0, min(1.0, score))

def retrieve_context_with_filter(
    question: str,
    student_context: Optional[Dict[str, Any]] = None
) -> tuple[Optional[str], str]:
    """
    Retrieve context with context-aware filtering
    
    استرجاع السياق مع التصفية الموجهة بالسياق
    
    Args:
        question: User's question / سؤال المستخدم
        student_context: Student context for filtering / سياق الطالب للتصفية
            {
                "major": "Software Engineering",
                "enrollment_year": 2022,
                "current_year": 3,
                "plan_version": "2022"
            }
    
    Returns:
        Tuple of (context_string, source_info) / مجموعة من (سلسلة_السياق، معلومات_المصدر)
    """
    try:
        cache_key = _cache_key(question + str(student_context or ""))
        cached = cache_manager.get(cache_key)
        if cached:
            return cached.get("context"), cached.get("source")
        
        logger.info(f"Retrieving context with filter for question: {question[:100]}")
        
        # Get documents with basic retrieval
        retrieved_docs = retriever.invoke(question)
        
        if not retrieved_docs:
            logger.warning("No documents retrieved from vectorstore")
            return None, "LLM (No RAG)"
        
        # Filter by context if provided
        if student_context:
            filtered_docs = []
            
            for doc in retrieved_docs:
                metadata = doc.metadata
                
                # Filter by plan version
                if "plan_version" in student_context:
                    doc_version = metadata.get("plan_version", "unknown")
                    student_version = student_context["plan_version"]
                    
                    # Match exact version or "all" or "unknown"
                    if doc_version not in [student_version, "all", "unknown"]:
                        continue
                
                # Filter by major (if available in metadata)
                if "major" in student_context and "major" in metadata:
                    if metadata["major"] != student_context["major"]:
                        continue
                
                # Filter by status (only active documents)
                if metadata.get("status") not in ["active", None]:
                    continue
                
                filtered_docs.append(doc)
            
            # Use filtered docs if any, otherwise use all
            if filtered_docs:
                retrieved_docs = filtered_docs
                logger.info(f"Filtered to {len(filtered_docs)} documents based on context")
        
        logger.info(f"Retrieved {len(retrieved_docs)} documents")
        source_info = ", ".join(list(set([doc.metadata.get("source", "Unknown") for doc in retrieved_docs])))
        context_str = "\n\n---\n\n".join([doc.page_content for doc in retrieved_docs])
        
        logger.info(f"Context length: {len(context_str)} characters from sources: {source_info}")
        response_payload = {"context": context_str, "source": f"RAG ({source_info})"}
        cache_manager.set(cache_key, response_payload, ttl_seconds=CACHE_TTL_SECONDS)
        return response_payload["context"], response_payload["source"]
        
    except Exception as e:
        logger.error(f"Error retrieving context with filter: {e}", exc_info=True)
        return None, "LLM (RAG Error)"
