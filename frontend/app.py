import streamlit as st
import requests
import os
import json
import socket
import pandas as pd
from typing import Dict, Any, Optional
from datetime import datetime

# ------------------------------------------------------------
# إعداد عنوان الواجهة الخلفية (من متغير البيئة في docker-compose)
# ------------------------------------------------------------

def get_backend_url():
    """الحصول على عنوان الواجهة الخلفية بناءً على البيئة."""
    backend_url = os.getenv("FASTAPI_BACKEND_URL")
    
    # إذا كان متغير البيئة موجوداً
    if backend_url:
        # إذا كان العنوان يحتوي على 'backend' (اسم الخدمة في Docker)
        if "backend" in backend_url:
            # التحقق من أننا داخل Docker (Linux)
            is_docker_linux = (
                os.path.exists("/.dockerenv") or  # Linux Docker
                os.path.exists("/proc/1/cgroup")  # Linux cgroup
            )
            
            # إذا كنا داخل Docker على Linux، استخدم العنوان كما هو
            if is_docker_linux:
                return backend_url
            
            # إذا كنا على Windows Docker أو خارج Docker
            # محاولة الاتصال الفعلي بـ backend أولاً
            try:
                # محاولة حل الاسم مع timeout قصير
                socket.setdefaulttimeout(0.5)
                socket.gethostbyname("backend")
                # إذا نجح حل الاسم، نحن داخل Docker network
                return backend_url
            except (socket.gaierror, OSError, socket.timeout):
                # إذا فشل حل الاسم، استخدم localhost
                return backend_url.replace("backend", "localhost")
        return backend_url
    
    # إذا لم يكن موجوداً، استخدم localhost (يعمل محلياً)
    return "http://localhost:8000"

BACKEND_URL = get_backend_url()

CHAT_ENDPOINT = f"{BACKEND_URL}/chat"
USERS_ENDPOINT = f"{BACKEND_URL}/users/"
PROGRESS_ENDPOINT = f"{BACKEND_URL}/progress/"
NOTIFICATIONS_ENDPOINT = f"{BACKEND_URL}/notifications/"
DOCS_ENDPOINT = f"{BACKEND_URL}/documents/"
GRAPH_ENDPOINT = f"{BACKEND_URL}/graph/"

# ------------------------------------------------------------
# إعداد الصفحة مع تحسينات UI
# ------------------------------------------------------------
st.set_page_config(
    layout="wide", 
    page_title="مرشدي الأكاديمي الذكي",
    page_icon="🎓",
    initial_sidebar_state="expanded"
)

# CSS مخصص لتحسين المظهر (ديناميكي حسب الوضع)
def get_theme_css(theme: str) -> str:
    """إرجاع CSS حسب الوضع المختار."""
    if theme == "light":
        return """
        <style>
            /* الوضع النهاري */
            .main {
                background-color: #ffffff;
            }
            .stButton>button {
                width: 100%;
                border-radius: 8px;
                border: none;
                padding: 0.5rem 1rem;
                font-weight: 600;
                transition: all 0.3s;
                background-color: #f0f2f6;
                color: #1f2937;
            }
            .stButton>button:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                background-color: #e5e7eb;
            }
            .stTextInput>div>div>input {
                border-radius: 8px;
                background-color: #ffffff;
                color: #1f2937;
            }
            .stSelectbox>div>div>select {
                border-radius: 8px;
                background-color: #ffffff;
                color: #1f2937;
            }
            .stTextArea>div>div>textarea {
                border-radius: 8px;
                background-color: #ffffff;
                color: #1f2937;
            }
            .stAlert {
                border-radius: 8px;
                padding: 1rem;
            }
            .stDataFrame {
                border-radius: 8px;
            }
            [data-testid="stSidebar"] {
                background-color: #f8f9fa;
            }
            h1, h2, h3 {
                color: #1f2937;
            }
            [data-testid="stMetricValue"] {
                font-size: 2rem;
            }
            .stMarkdown {
                color: #1f2937;
            }
            /* Chat message styling */
            .stChatMessage {
                padding: 1rem;
                border-radius: 12px;
                margin-bottom: 1rem;
            }
            .stChatMessage[data-testid="user"] {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }
            .stChatMessage[data-testid="assistant"] {
                background: rgba(59, 130, 246, 0.1);
                border-left: 3px solid #3b82f6;
            }
            /* Smooth animations */
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }
            .stChatMessage {
                animation: fadeIn 0.3s ease-in;
            }
            /* Code blocks styling */
            pre {
                background: rgba(0, 0, 0, 0.05);
                padding: 1rem;
                border-radius: 8px;
                overflow-x: auto;
            }
            /* Links styling */
            a {
                color: #3b82f6;
                text-decoration: none;
            }
            a:hover {
                text-decoration: underline;
            }
        </style>
        """
    else:
        return """
        <style>
            /* الوضع الليلي */
            .main {
                background-color: #0e1117;
            }
            .stButton>button {
                width: 100%;
                border-radius: 8px;
                border: none;
                padding: 0.5rem 1rem;
                font-weight: 600;
                transition: all 0.3s;
                background-color: #262730;
                color: #ffffff;
            }
            .stButton>button:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 8px rgba(0,0,0,0.2);
                background-color: #3a3d4a;
            }
            .stTextInput>div>div>input {
                border-radius: 8px;
                background-color: #262730;
                color: #ffffff;
            }
            .stSelectbox>div>div>select {
                border-radius: 8px;
                background-color: #262730;
                color: #ffffff;
            }
            .stTextArea>div>div>textarea {
                border-radius: 8px;
                background-color: #262730;
                color: #ffffff;
            }
            .stAlert {
                border-radius: 8px;
                padding: 1rem;
            }
            .stDataFrame {
                border-radius: 8px;
            }
            [data-testid="stSidebar"] {
                background-color: #1e2130;
            }
            h1, h2, h3 {
                color: #ffffff;
            }
            [data-testid="stMetricValue"] {
                font-size: 2rem;
            }
            .stMarkdown {
                color: #ffffff;
            }
            /* Chat message styling */
            .stChatMessage {
                padding: 1rem;
                border-radius: 12px;
                margin-bottom: 1rem;
            }
            .stChatMessage[data-testid="user"] {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }
            .stChatMessage[data-testid="assistant"] {
                background: rgba(59, 130, 246, 0.1);
                border-left: 3px solid #3b82f6;
            }
            /* Smooth animations */
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }
            .stChatMessage {
                animation: fadeIn 0.3s ease-in;
            }
            /* Code blocks styling */
            pre {
                background: rgba(0, 0, 0, 0.1);
                padding: 1rem;
                border-radius: 8px;
                overflow-x: auto;
            }
            /* Links styling */
            a {
                color: #3b82f6;
                text-decoration: none;
            }
            a:hover {
                text-decoration: underline;
            }
        </style>
        """

# ------------------------------------------------------------
# الترجمات (Translations) - يجب تعريفه قبل الاستخدام
# ------------------------------------------------------------
TRANSLATIONS = {
    "ar": {
        "app_title": "مرشدي الأكاديمي الذكي",
        "login": "تسجيل الدخول",
        "register": "تسجيل جديد",
        "logout": "تسجيل الخروج",
        "welcome": "مرحباً",
        "role": "الدور",
        "choose_service": "اختر الخدمة",
        "smart_chat": "الدردشة الذكية",
        "progress_analysis": "تحليل التقدم",
        "gpa_simulator": "محاكي المعدل",
        "notifications": "الإشعارات",
        "skills_graph": "الرسم البياني للمهارات",
        "data_guide": "دليل البيانات",
        "settings": "الإعدادات",
        "theme": "الوضع",
        "language": "اللغة",
        "dark_mode": "ليلي",
        "light_mode": "نهاري",
        "arabic": "العربية",
        "english": "English",
    },
    "en": {
        "app_title": "My Smart Academic Advisor",
        "login": "Login",
        "register": "Register",
        "logout": "Logout",
        "welcome": "Welcome",
        "role": "Role",
        "choose_service": "Choose Service",
        "smart_chat": "Smart Chat",
        "progress_analysis": "Progress Analysis",
        "gpa_simulator": "GPA Simulator",
        "notifications": "Notifications",
        "skills_graph": "Skills Graph",
        "data_guide": "Data Guide",
        "settings": "Settings",
        "theme": "Theme",
        "language": "Language",
        "dark_mode": "Dark",
        "light_mode": "Light",
        "arabic": "العربية",
        "english": "English",
    }
}

# ------------------------------------------------------------
# تهيئة حالة واجهة المستخدم (Session State) - يجب أن يكون قبل أي استخدام
# ------------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "user_role" not in st.session_state:
    st.session_state.user_role = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_gpa" not in st.session_state:
    st.session_state.current_gpa = 0.0
if "completed_hours" not in st.session_state:
    st.session_state.completed_hours = 0
if "theme" not in st.session_state:
    st.session_state.theme = "dark"  # dark أو light
if "language" not in st.session_state:
    st.session_state.language = "ar"  # ar أو en

def t(key: str) -> str:
    """الحصول على الترجمة حسب اللغة الحالية."""
    return TRANSLATIONS.get(st.session_state.language, TRANSLATIONS["ar"]).get(key, key)

# تطبيق CSS ديناميكي - يجب أن يكون بعد تهيئة session_state
# يتم تطبيقه في كل مرة يتم فيها تحميل الصفحة
st.markdown(get_theme_css(st.session_state.theme), unsafe_allow_html=True)

# تحديث العنوان حسب اللغة
app_title = TRANSLATIONS.get(st.session_state.language, TRANSLATIONS["ar"]).get("app_title", "مرشدي الأكاديمي الذكي")
# تحديث العنوان في Sidebar (يتم تحديثه تلقائياً عند تغيير اللغة)
if "sidebar_title_set" not in st.session_state:
    st.sidebar.title(f"🎓 {app_title}")
    st.session_state.sidebar_title_set = True
elif st.session_state.get("language_changed", False):
    st.sidebar.title(f"🎓 {app_title}")
    st.session_state.language_changed = False

# ------------------------------------------------------------
# وظائف مساعدة محسّنة
# ------------------------------------------------------------

def safe_json_parse(response: requests.Response) -> Optional[Dict[str, Any]]:
    """محاولة تحليل JSON بشكل آمن."""
    try:
        return response.json()
    except (json.JSONDecodeError, ValueError):
        try:
            text = response.text[:200] if response.text else "خطأ غير معروف"
            # محاولة تحليل JSON إذا كان النص يحتوي على JSON
            if text.startswith('[') or text.startswith('{'):
                try:
                    return json.loads(text)
                except:
                    pass
            return {"detail": text}
        except:
            return {"detail": "خطأ غير معروف"}

def post_request(endpoint: str, data: Dict[str, Any], headers: Optional[Dict[str, str]] = None, timeout: int = 300, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """إرسال طلب POST إلى الواجهة الخلفية مع معالجة محسّنة للأخطاء."""
    try:
        response = requests.post(endpoint, json=data, headers=headers, timeout=timeout, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        error_detail = "خطأ غير معروف"
        if e.response is not None:
            try:
                error_data = safe_json_parse(e.response)
                # معالجة تفصيلية لرسائل الخطأ
                if isinstance(error_data, dict):
                    detail = error_data.get('detail', '')
                    if isinstance(detail, list):
                        # إذا كان detail قائمة من الأخطاء
                        error_messages = []
                        for err in detail:
                            if isinstance(err, dict):
                                msg = err.get('msg', '')
                                loc = err.get('loc', [])
                                if msg:
                                    error_messages.append(f"{'.'.join(map(str, loc))}: {msg}")
                        error_detail = "; ".join(error_messages) if error_messages else f'خطأ HTTP {e.response.status_code}'
                    else:
                        error_detail = str(detail) if detail else f'خطأ HTTP {e.response.status_code}'
                elif isinstance(error_data, list):
                    # إذا كان error_data قائمة مباشرة
                    error_messages = []
                    for err in error_data:
                        if isinstance(err, dict):
                            msg = err.get('msg', '')
                            loc = err.get('loc', [])
                            if msg:
                                error_messages.append(f"{'.'.join(map(str, loc))}: {msg}")
                    error_detail = "; ".join(error_messages) if error_messages else f'خطأ HTTP {e.response.status_code}'
                else:
                    error_detail = str(error_data) if error_data else f'خطأ HTTP {e.response.status_code}'
            except Exception as parse_error:
                error_detail = f'خطأ HTTP {e.response.status_code}: {str(parse_error)[:100]}'
        st.error(f"❌ خطأ HTTP: {error_detail}")
        return None
    except requests.exceptions.Timeout:
        st.error("⏱️ انتهت مهلة الاتصال. يرجى المحاولة مرة أخرى.")
        return None
    except requests.exceptions.ConnectionError:
        st.error("🔌 فشل الاتصال بالواجهة الخلفية. تأكد من أن الخدمة تعمل.")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"⚠️ خطأ في الاتصال: {str(e)[:100]}")
        return None
    except Exception as e:
        st.error(f"❌ خطأ غير متوقع: {str(e)[:100]}")
        return None

def get_request(endpoint: str, headers: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
    """إرسال طلب GET إلى الواجهة الخلفية مع معالجة محسّنة للأخطاء."""
    try:
        response = requests.get(endpoint, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        error_detail = "خطأ غير معروف"
        if e.response is not None:
            try:
                error_data = safe_json_parse(e.response)
                # معالجة تفصيلية لرسائل الخطأ
                if isinstance(error_data, dict):
                    detail = error_data.get('detail', '')
                    if isinstance(detail, list):
                        error_messages = []
                        for err in detail:
                            if isinstance(err, dict):
                                msg = err.get('msg', '')
                                loc = err.get('loc', [])
                                if msg:
                                    error_messages.append(f"{'.'.join(map(str, loc))}: {msg}")
                        error_detail = "; ".join(error_messages) if error_messages else f'خطأ HTTP {e.response.status_code}'
                    else:
                        error_detail = str(detail) if detail else f'خطأ HTTP {e.response.status_code}'
                elif isinstance(error_data, list):
                    error_messages = []
                    for err in error_data:
                        if isinstance(err, dict):
                            msg = err.get('msg', '')
                            loc = err.get('loc', [])
                            if msg:
                                error_messages.append(f"{'.'.join(map(str, loc))}: {msg}")
                    error_detail = "; ".join(error_messages) if error_messages else f'خطأ HTTP {e.response.status_code}'
                else:
                    error_detail = str(error_data) if error_data else f'خطأ HTTP {e.response.status_code}'
            except Exception as parse_error:
                error_detail = f'خطأ HTTP {e.response.status_code}: {str(parse_error)[:100]}'
        st.error(f"❌ خطأ HTTP: {error_detail}")
        return None
    except requests.exceptions.Timeout:
        st.error("⏱️ انتهت مهلة الاتصال. يرجى المحاولة مرة أخرى.")
        return None
    except requests.exceptions.ConnectionError:
        st.error("🔌 فشل الاتصال بالواجهة الخلفية. تأكد من أن الخدمة تعمل.")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"⚠️ خطأ في الاتصال: {str(e)[:100]}")
        return None
    except Exception as e:
        st.error(f"❌ خطأ غير متوقع: {str(e)[:100]}")
        return None

# ------------------------------------------------------------
# وظائف الإعداد الأولي (للتجربة)
# ------------------------------------------------------------

def setup_initial_data():
    """إعداد بيانات فهرسة المستندات (للمسؤولين فقط)."""
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ الإعداد الأولي (للمسؤول)")
    
    if st.session_state.user_role == "admin":

        # 2. فهرسة المستندات
        if st.sidebar.button("📄 فهرسة المستندات (RAG)", use_container_width=True):
            with st.sidebar:
                progress_bar = st.progress(0)
                status_text = st.empty()
                status_text.info("⏳ جاري فهرسة المستندات... قد يستغرق هذا بعض الوقت")
                
                headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
                # استخدام timeout أطول (5 دقائق) لفهرسة المستندات
                result = post_request(f"{DOCS_ENDPOINT}ingest", {}, headers=headers, timeout=300)
                
                progress_bar.progress(100)
                status_text.empty()
                
                if result:
                    if result.get("status") == "success":
                        st.sidebar.success(f"✅ {result.get('message', 'تمت الفهرسة بنجاح')}")
                    else:
                        error_msg = result.get("message", "فشل فهرسة المستندات")
                        st.sidebar.error(f"❌ {error_msg}")
                else:
                    st.sidebar.error("❌ فشل فهرسة المستندات. تحقق من أن Ollama يعمل وأن هناك مستندات في مجلد /app/data")
                
        # 3. فهرسة الرسم البياني
        if st.sidebar.button("🌳 فهرسة الرسم البياني (Neo4j)", use_container_width=True):
            with st.sidebar:
                status_text = st.empty()
                status_text.info("⏳ جاري فهرسة الرسم البياني...")
                
                headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
                result = post_request(f"{GRAPH_ENDPOINT}ingest", {}, headers=headers, timeout=120)
                
                status_text.empty()
                
                if result:
                    if result.get("status") == "success":
                        st.sidebar.success(f"✅ {result.get('message', 'تمت الفهرسة بنجاح')}")
                    else:
                        error_msg = result.get("message", "فشل فهرسة الرسم البياني")
                        st.sidebar.error(f"❌ {error_msg}")
                else:
                    st.sidebar.error("❌ فشل فهرسة الرسم البياني. تحقق من أن Neo4j يعمل")
    else:
        st.sidebar.info("ℹ️ يجب أن تكون مسؤولاً لتنفيذ الإعداد الأولي.")

# ------------------------------------------------------------
# واجهة الدردشة (Chatbot)
# ------------------------------------------------------------

def chat_interface():
    """
    Professional chat interface similar to Gemini/ChatGPT.
    / واجهة دردشة احترافية مشابهة لـ Gemini/ChatGPT.
    """
    # Header with better styling
    st.markdown("""
    <div style='text-align: center; padding: 1rem 0;'>
        <h1 style='margin: 0; font-size: 2.5rem; background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
                    -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>
            💬 مرشد الدردشة الذكي
        </h1>
        <p style='color: #6b7280; margin-top: 0.5rem; font-size: 1.1rem;'>
            Agentic RAG - اسأل عن اللوائح، خطتك الدراسية، أو المهارات المطلوبة
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # التحقق من الوضع التجريبي
    is_demo = st.session_state.user_id.startswith("demo_") if st.session_state.user_id else False
    if is_demo:
        st.info("""
        ⚠️ **وضع تجريبي:** أنت تستخدم الوضع التجريبي. 
        لن تتمكن من الوصول إلى بياناتك الشخصية أو الميزات المتقدمة.
        """)
    
    # Toolbar with actions
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("🗑️ مسح", use_container_width=True, help="مسح جميع الرسائل"):
            st.session_state.messages = []
            st.rerun()
    with col2:
        if st.button("📋 نسخ", use_container_width=True, help="نسخ المحادثة"):
            if st.session_state.messages:
                try:
                    import pyperclip
                    chat_text = "\n\n".join([f"{msg['role']}: {msg['content']}" for msg in st.session_state.messages])
                    pyperclip.copy(chat_text)
                    st.success("تم النسخ!")
                except ImportError:
                    st.info("💡 استخدم Ctrl+C للنسخ يدوياً")
                except Exception:
                    st.info("💡 استخدم Ctrl+C للنسخ يدوياً")

    # Chat container with better styling
    st.markdown("---")
    
    # عرض الرسائل السابقة في سجل المحادثة مع تنسيق محسّن
    if not st.session_state.messages:
        # Welcome message
        st.markdown("""
        <div style='text-align: center; padding: 3rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    border-radius: 15px; margin: 2rem 0; color: white;'>
            <h2 style='color: white; margin-bottom: 1rem;'>🎓 مرحباً بك في المرشد الأكاديمي الذكي</h2>
            <p style='font-size: 1.2rem; opacity: 0.9;'>
                يمكنك أن تسألني عن أي شيء متعلق بدراستك الأكاديمية
            </p>
            <div style='margin-top: 2rem; display: flex; justify-content: center; gap: 1rem; flex-wrap: wrap;'>
                <span style='background: rgba(255,255,255,0.2); padding: 0.5rem 1rem; border-radius: 20px;'>📚 اللوائح والخطط</span>
                <span style='background: rgba(255,255,255,0.2); padding: 0.5rem 1rem; border-radius: 20px;'>📊 التقدم الأكاديمي</span>
                <span style='background: rgba(255,255,255,0.2); padding: 0.5rem 1rem; border-radius: 20px;'>🎯 المهارات</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        for idx, message in enumerate(st.session_state.messages):
            with st.chat_message(message["role"]):
                # Enhanced markdown rendering
                content = message["content"]
                
                # Parse and format the response better
                if message["role"] == "assistant" and "**النية المحددة:**" in content:
                    # Split intent, answer, and source
                    parts = content.split("**النية المحددة:**")
                    if len(parts) > 1:
                        intent_part = parts[1].split("\n\n")[0].strip().replace("`", "")
                        answer_part = "\n\n".join(parts[1].split("\n\n")[1:])
                        
                        # Remove source from answer if exists
                        if "*(مصدر المعلومة:" in answer_part:
                            answer_part = answer_part.split("*(مصدر المعلومة:")[0].strip()
                            source_part = content.split("*(مصدر المعلومة:")[1].replace(")*", "").strip()
                        else:
                            source_part = None
                        
                        # Display intent badge
                        intent_colors = {
                            "query_rag": "#3b82f6",
                            "analyze_progress": "#10b981",
                            "simulate_gpa": "#f59e0b",
                            "graph_query": "#8b5cf6",
                            "general_chat": "#6b7280"
                        }
                        intent_label = intent_part.replace("`", "").strip()
                        intent_color = intent_colors.get(intent_label, "#6b7280")
                        
                        st.markdown(f"""
                        <div style='display: inline-block; background: {intent_color}; color: white; 
                                    padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.85rem; 
                                    margin-bottom: 1rem; font-weight: 500;'>
                            🎯 {intent_label}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Display answer with better formatting
                        st.markdown(answer_part)
                        
                        # Display source if available
                        if source_part:
                            st.markdown(f"""
                            <div style='margin-top: 1rem; padding: 0.75rem; background: rgba(59, 130, 246, 0.1);
                                        border-left: 3px solid #3b82f6; border-radius: 5px; font-size: 0.9rem;'>
                                📄 <strong>المصدر:</strong> {source_part}
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.markdown(content)
                else:
                    st.markdown(content)

    # إدخال المستخدم مع placeholder محسّن
    prompt = st.chat_input("💬 اسأل سؤالك هنا... (مثال: ما هي متطلبات التخرج؟)")

    if prompt:
        # 1️⃣ أضف رسالة المستخدم إلى واجهة المستخدم فوراً
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2️⃣ أرسل الرسالة إلى الواجهة الخلفية (FastAPI)
        with st.chat_message("assistant"):
            # Enhanced loading indicator
            with st.spinner("🤔 أفكر في إجابتك... قد يستغرق هذا بضع ثوانٍ"):
                data = {"question": prompt, "user_id": st.session_state.user_id}
                headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
                # زيادة timeout للدردشة إلى 120 ثانية
                response_data = post_request(CHAT_ENDPOINT, data, headers=headers, timeout=120)

                if response_data:
                    answer = response_data.get("answer", "حدث خطأ في معالجة الرد.")
                    source = response_data.get("source", "غير معروف")
                    intent = response_data.get("intent", "غير محدد")
                    demo_warning = response_data.get("demo_warning", "")
                    
                    # Check if response is from FAQ (URAG)
                    is_faq = "FAQ" in source or response_data.get("mode") == "faq"
                    faq_confidence = response_data.get("confidence")

                    # Format response with better structure
                    intent_colors = {
                        "query_rag": "#3b82f6",
                        "analyze_progress": "#10b981",
                        "simulate_gpa": "#f59e0b",
                        "graph_query": "#8b5cf6",
                        "general_chat": "#6b7280"
                    }
                    intent_color = intent_colors.get(intent, "#6b7280")
                    
                    # Display FAQ badge if from FAQ (URAG)
                    if is_faq:
                        st.markdown(f"""
                        <div style='display: inline-block; background: #10b981; color: white; 
                                    padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.85rem; 
                                    margin-bottom: 1rem; font-weight: 500; margin-left: 0.5rem;'>
                            ✓ إجابة دقيقة 100% من اللوائح
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Display intent badge
                    st.markdown(f"""
                    <div style='display: inline-block; background: {intent_color}; color: white; 
                                padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.85rem; 
                                margin-bottom: 1rem; font-weight: 500;'>
                        🎯 {intent}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Display answer
                    st.markdown(answer)
                    
                    # Display demo warning if exists
                    if demo_warning:
                        st.warning(demo_warning)
                    
                    # Display source with better styling
                    source_color = "#10b981" if is_faq else "#3b82f6"
                    source_icon = "✓" if is_faq else "📄"
                    source_label = "مصدر دقيق 100%" if is_faq else "المصدر"
                    
                    st.markdown(f"""
                    <div style='margin-top: 1rem; padding: 0.75rem; background: rgba(59, 130, 246, 0.1);
                                border-left: 3px solid {source_color}; border-radius: 5px; font-size: 0.9rem;'>
                        {source_icon} <strong>{source_label}:</strong> {source}
                    </div>
                    """, unsafe_allow_html=True)

                    # Store full response for history
                    full_response = f"**النية المحددة:** `{intent}`\n\n{answer}"
                    if demo_warning:
                        full_response += f"\n\n{demo_warning}"
                    full_response += f"\n\n*(مصدر المعلومة: {source})*"
                    
                    # أضف رد المساعد إلى سجل الجلسة
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": full_response
                    })
                else:
                    error_msg = "❌ فشل في الحصول على رد من خدمة الدردشة. يرجى المحاولة مرة أخرى."
                    st.error(error_msg)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_msg
                    })

# ------------------------------------------------------------
# واجهة تحليل التقدم (Progress Analysis)
# ------------------------------------------------------------

def sync_data_interface():
    """واجهة جمع البيانات من النظام الجامعي"""
    st.header("🔄 جمع البيانات من النظام الجامعي")
    st.caption("قم بجمع أحدث بياناتك من النظام الجامعي وتحديث معلوماتك الأكاديمية.")
    
    # التحقق من الوضع التجريبي
    is_demo = st.session_state.user_id.startswith("demo_") if st.session_state.user_id else False
    if is_demo:
        st.warning("⚠️ **وضع تجريبي:** هذه الميزة غير متاحة في الوضع التجريبي. يرجى تسجيل الدخول بالبيانات الصحيحة.")
        st.stop()
    
    # التحقق من أن المستخدم طالب
    if st.session_state.user_role != "student":
        st.error("❌ هذه الميزة متاحة للطلاب فقط.")
        st.stop()
    
    st.info("💡 سيتم جمع جميع بياناتك من النظام الجامعي بما في ذلك الدرجات والمقررات والمعدل التراكمي.")
    st.warning("⚠️ **ملاحظة:** إذا فشل الاتصال بالنظام الجامعي، سيتم عرض رسالة خطأ واضحة.")
    
    with st.form("sync_data_form"):
        password = st.text_input("كلمة المرور", type="password", key="sync_password", placeholder="أدخل كلمة سر النظام الجامعي")
        submitted = st.form_submit_button("🔄 جمع البيانات من النظام الجامعي", use_container_width=True, type="primary")
        
        if submitted:
            if not password:
                st.error("❌ يرجى إدخال كلمة المرور.")
            else:
                with st.spinner("⏳ جاري جمع البيانات من النظام الجامعي... قد يستغرق هذا بعض الوقت"):
                    sync_data = {"password": password}
                    headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
                    response = post_request(f"{BACKEND_URL}/users/sync-data", sync_data, headers=headers)
                    
                    if response and response.get("success"):
                        st.success("✅ تم جمع البيانات بنجاح!")
                        data = response.get("data", {})
                        st.markdown("---")
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("المعدل التراكمي", f"{data.get('gpa', 0):.2f}" if data.get('gpa') else "غير متوفر")
                        with col2:
                            st.metric("الساعات المكتملة", data.get('completed_hours', 0))
                        with col3:
                            st.metric("عدد المقررات", data.get('courses_count', 0))
                    else:
                        error_msg = response.get("detail", "فشل جمع البيانات") if response else "فشل جمع البيانات"
                        st.error(f"❌ {error_msg}")

def progress_analysis_interface():
    st.header("📊 تحليل التقدم الأكاديمي")
    st.caption("اعرض تحليلاً مفصلاً لسجلك الأكاديمي وتقدمك الدراسي.")
    
    # التحقق من الوضع التجريبي
    is_demo = st.session_state.user_id.startswith("demo_") if st.session_state.user_id else False
    if is_demo:
        st.warning("⚠️ **وضع تجريبي:** هذه الميزة غير متاحة في الوضع التجريبي. يرجى تسجيل الدخول بالبيانات الصحيحة.")
        st.stop()
    
    col1, col2 = st.columns([1, 4])
    with col1:
        analyze_btn = st.button("🔍 تحليل سجلي الأكاديمي", use_container_width=True, type="primary")
    
    if analyze_btn:
        st.markdown("---")
        st.subheader("📈 نتائج التحليل")
        with st.spinner("⏳ جاري تحليل السجل الأكاديمي..."):
            headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
            analysis_result = get_request(f"{PROGRESS_ENDPOINT}analyze/{st.session_state.user_id}", headers=headers)
            
            if analysis_result:
                st.session_state.current_gpa = analysis_result.get("current_gpa", 0.0)
                st.session_state.completed_hours = analysis_result.get("completed_hours", 0)
                
                # عرض المقاييس بشكل جميل
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(
                        "المعدل التراكمي (GPA)", 
                        f"{st.session_state.current_gpa:.2f}",
                        delta=f"{st.session_state.current_gpa - 2.0:.2f}" if st.session_state.current_gpa >= 2.0 else None
                    )
                with col2:
                    st.metric("الساعات المكتملة", analysis_result.get("completed_hours", 0))
                with col3:
                    st.metric("المقررات المتبقية", analysis_result.get("remaining_courses_count", 0))
                
                st.markdown("---")
                
                # المقررات القابلة للتسجيل
                st.subheader("📚 المقررات القابلة للتسجيل في الفصل القادم")
                registerable_courses = analysis_result.get("registerable_next_semester", [])
                if registerable_courses:
                    st.dataframe(registerable_courses, use_container_width=True)
                else:
                    st.info("ℹ️ لا توجد مقررات قابلة للتسجيل حالياً بناءً على الخطة الدراسية.")
                
                st.markdown("---")
                
                # سجل المقررات المكتملة
                st.subheader("✅ سجل المقررات المكتملة")
                completed_courses = analysis_result.get("completed_courses", {})
                if completed_courses:
                    st.json(completed_courses)
                else:
                    st.info("ℹ️ لا توجد مقررات مكتملة مسجلة.")
            else:
                st.error("❌ فشل في تحليل السجل الأكاديمي. تأكد من إنشاء مستخدم تجريبي وإضافة سجلات دراسية.")

# ------------------------------------------------------------
# واجهة محاكاة المعدل (GPA Simulator)
# ------------------------------------------------------------

def gpa_simulator_interface():
    st.header("🧮 محاكي المعدل التراكمي")
    st.caption("توقع معدلك التراكمي بناءً على درجاتك المتوقعة في الفصل الحالي.")
    
    with st.form("gpa_simulation_form"):
        st.subheader("📋 بياناتك الحالية")
        col1, col2 = st.columns(2)
        with col1:
            current_gpa = st.number_input(
                "المعدل التراكمي الحالي", 
                min_value=0.0, 
                max_value=4.0, 
                value=st.session_state.current_gpa, 
                step=0.01,
                help="أدخل معدلك التراكمي الحالي"
            )
        with col2:
            current_hours = st.number_input(
                "إجمالي الساعات المكتملة", 
                min_value=0, 
                value=st.session_state.completed_hours, 
                step=1,
                help="أدخل إجمالي الساعات المكتملة"
            )
        
        st.markdown("---")
        st.subheader("📖 المقررات المتوقعة لهذا الفصل")
        
        col1, col2 = st.columns(2)
        with col1:
            new_courses_input = st.text_area(
                "أدخل المقررات وعدد ساعاتها",
                value="CS201:3, AI300:3",
                help="مثال: CS201:3, AI300:3, MATH202:4"
            )
        with col2:
            expected_grades_input = st.text_area(
                "أدخل الدرجات المتوقعة",
                value="CS201:A, AI300:B+",
                help="مثال: CS201:A, AI300:B+, MATH202:B"
            )
        
        submitted = st.form_submit_button("🧮 حساب المعدل المتوقع", use_container_width=True, type="primary")
        
        if submitted:
            try:
                # معالجة مدخلات المقررات
                new_courses = {}
                for item in new_courses_input.split(','):
                    if ':' in item:
                        code, hours = item.strip().split(':')
                        new_courses[code.strip()] = int(hours.strip())
                
                # معالجة مدخلات الدرجات
                expected_grades = {}
                for item in expected_grades_input.split(','):
                    if ':' in item:
                        code, grade = item.strip().split(':')
                        expected_grades[code.strip()] = grade.strip().upper()
                
                if not new_courses or not expected_grades:
                    st.error("❌ يرجى إدخال المقررات والدرجات بشكل صحيح.")
                    st.stop()
                
                simulation_data = {
                    "current_gpa": current_gpa,
                    "current_hours": current_hours,
                    "new_courses": new_courses,
                    "expected_grades": expected_grades
                }
                
                with st.spinner("⏳ جاري محاكاة المعدل..."):
                    headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
                    result = post_request(f"{PROGRESS_ENDPOINT}simulate-gpa", simulation_data, headers=headers)
                    
                    if result:
                        st.success("✅ تمت المحاكاة بنجاح!")
                        st.markdown("---")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric(
                                "المعدل التراكمي بعد الفصل", 
                                f"{result.get('future_gpa', 0):.2f}",
                                delta=f"{result.get('future_gpa', 0) - current_gpa:.2f}"
                            )
                        with col2:
                            st.metric(
                                "إجمالي الساعات بعد الفصل", 
                                result.get('total_hours_after_semester', 0)
                            )
                    else:
                        st.error("❌ فشل في محاكاة المعدل.")
                        
            except ValueError as e:
                st.error(f"❌ خطأ في تنسيق الإدخال: {str(e)}. يرجى التأكد من اتباع التنسيق الصحيح.")
            except Exception as e:
                st.error(f"❌ خطأ غير متوقع: {str(e)}")

# ------------------------------------------------------------
# واجهة الإشعارات (Notifications)
# ------------------------------------------------------------

def notifications_interface():
    st.header("🔔 الإشعارات والتنبيهات")
    st.caption("اعرض آخر الإشعارات والتنبيهات المتعلقة بسجلك الأكاديمي.")
    
    col1, col2 = st.columns([1, 4])
    with col1:
        refresh_btn = st.button("🔄 تحديث الإشعارات", use_container_width=True, type="primary")
    
    if refresh_btn:
        with st.spinner("⏳ جاري جلب الإشعارات..."):
            headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
            notifications = get_request(f"{NOTIFICATIONS_ENDPOINT}{st.session_state.user_id}", headers=headers)
            
            if notifications is not None:
                if notifications:
                    st.markdown("---")
                    for notif in notifications:
                        notif_type = notif.get('type', 'info')
                        message = notif.get('message', '')
                        created_at = notif.get('created_at', '')
                        
                        # تنسيق التاريخ
                        try:
                            if created_at:
                                date_str = created_at[:10] if len(created_at) >= 10 else created_at
                            else:
                                date_str = "غير محدد"
                        except:
                            date_str = "غير محدد"
                        
                        if notif_type == 'alert':
                            st.warning(f"⚠️ **تنبيه:** {message} *(بتاريخ: {date_str})*")
                        elif notif_type == 'recommendation':
                            st.info(f"💡 **توصية:** {message} *(بتاريخ: {date_str})*")
                        else:
                            st.success(f"✅ **إشعار:** {message} *(بتاريخ: {date_str})*")
                else:
                    st.info("ℹ️ لا توجد إشعارات جديدة.")
            else:
                st.error("❌ فشل في جلب الإشعارات.")

# ------------------------------------------------------------
# واجهة الرسم البياني (Graph)
# ------------------------------------------------------------

def graph_interface():
    st.header("🌳 تحليل الرسم البياني للمهارات")
    st.caption("استكشف المهارات المكتسبة من المقررات.")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        course_code = st.text_input(
            "أدخل رمز المقرر", 
            value="CS101",
            help="مثال: CS101, MATH202, AI300"
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        search_btn = st.button("🔍 عرض المهارات", use_container_width=True, type="primary")
    
    if search_btn:
        if not course_code.strip():
            st.warning("⚠️ يرجى إدخال رمز المقرر.")
            st.stop()
            
        with st.spinner(f"⏳ جاري جلب مهارات المقرر {course_code}..."):
            headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
            result = get_request(f"{GRAPH_ENDPOINT}skills/{course_code}", headers=headers)
            
            if result and result.get("skills"):
                skills = result["skills"]
                st.success(f"✅ المقرر **{course_code}** يدرس المهارات التالية:")
                st.markdown("---")
                
                # عرض المهارات بشكل جميل
                skills_text = ", ".join([f"**{s}**" for s in skills])
                st.markdown(f"🎯 {skills_text}")
            else:
                st.warning(f"⚠️ لم يتم العثور على مهارات للمقرر {course_code} أو فشل الاتصال بقاعدة بيانات الرسم البياني.")

# ------------------------------------------------------------
# واجهة تسجيل الدخول/التسجيل
# ------------------------------------------------------------

def login_interface():
    st.header("🔐 تسجيل الدخول / التسجيل")
    st.caption("سجل الدخول إلى حسابك أو أنشئ حساباً جديداً")
    
    tab1, tab2, tab3 = st.tabs(["🔑 تسجيل الدخول", "📝 تسجيل طالب جديد", "👤 تسجيل أدمن (للمسؤولين)"])
    
    with tab1:
        st.subheader("تسجيل الدخول")
        st.info("💡 **للطالب:** استخدم الرقم الجامعي وكلمة سر نظام الليرناتا\n\n**للأدمن:** استخدم البريد الإلكتروني وكلمة المرور")
        
        with st.form("login_form"):
            identifier = st.text_input(
                "الرقم الجامعي (للطالب) أو البريد الإلكتروني (للأدمن)", 
                key="login_identifier", 
                placeholder="مثال: 4210380 أو admin@example.com"
            )
            password = st.text_input(
                "كلمة المرور", 
                type="password", 
                key="login_password", 
                placeholder="أدخل كلمة المرور"
            )
            
            col1, col2 = st.columns([3, 1])
            with col1:
                submitted = st.form_submit_button("🔑 تسجيل الدخول", use_container_width=True, type="primary")
            with col2:
                demo_mode = st.checkbox("وضع تجريبي", key="demo_mode", help="استخدم الوضع التجريبي إذا فشل تسجيل الدخول")
            
            if submitted:
                if not identifier or not password:
                    st.error("❌ يرجى إدخال المعرف وكلمة المرور.")
                else:
                    with st.spinner("⏳ جاري تسجيل الدخول..."):
                        login_data = {"identifier": identifier.strip(), "password": password}
                        token_endpoint = f"{BACKEND_URL}/token/json"
                        
                        # إرسال الطلب مع معالجة أفضل للأخطاء
                        try:
                            response = post_request(
                                token_endpoint, 
                                login_data, 
                                params={"allow_demo": "true" if demo_mode else "false"}
                            )
                            
                            if response and response.get("access_token"):
                                st.session_state.logged_in = True
                                st.session_state.access_token = response["access_token"]
                                st.session_state.user_id = response["user_id"]
                                st.session_state.user_role = response.get("role", "student")
                                is_demo = response.get("is_demo", False)
                                
                                if is_demo:
                                    st.warning("⚠️ **وضع تجريبي:** أنت تستخدم الوضع التجريبي. لن تتمكن من الوصول إلى الميزات الشخصية.")
                                else:
                                    st.success(f"✅ تم تسجيل الدخول بنجاح كـ {st.session_state.user_role}!")
                                    
                                    # محاولة جمع البيانات من النظام الجامعي تلقائياً بعد تسجيل الدخول (فقط للطلاب وليس الوضع التجريبي)
                                    if st.session_state.user_role == "student" and not is_demo:
                                        with st.spinner("⏳ جاري جمع بياناتك من النظام الجامعي..."):
                                            sync_data = {"password": password}
                                            headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
                                            sync_response = post_request(f"{BACKEND_URL}/users/sync-data", sync_data, headers=headers, timeout=60)
                                            if sync_response and sync_response.get("success"):
                                                st.success("✅ تم جمع بياناتك بنجاح من النظام الجامعي!")
                                            else:
                                                error_msg = sync_response.get("detail", "فشل جمع البيانات") if sync_response else "فشل الاتصال بالخادم"
                                                st.warning(f"⚠️ تم تسجيل الدخول بنجاح، لكن فشل جمع البيانات: {error_msg}. يمكنك المحاولة لاحقاً من القائمة.")
                                
                                st.rerun()
                            else:
                                # معالجة أفضل لرسائل الخطأ
                                error_detail = response.get("detail", "فشل تسجيل الدخول") if response else "فشل الاتصال بالخادم"
                                st.error(f"❌ {error_detail}")
                                if "الرقم الجامعي أو كلمة المرور غير صحيحة" in str(error_detail):
                                    st.info("💡 يمكنك تفعيل الوضع التجريبي للاستكشاف بدون بيانات شخصية.")
                        except Exception as e:
                            st.error(f"❌ خطأ في الاتصال: {str(e)[:200]}")
                            st.info("💡 تأكد من أن الخادم يعمل وأن البيانات المدخلة صحيحة.")

    with tab2:
        st.subheader("📝 تسجيل طالب جديد")
        st.info("💡 **للطلاب فقط:** سيتم التحقق من بياناتك في النظام الجامعي تلقائياً")
        
        with st.form("register_student_form"):
            user_id = st.text_input(
                "الرقم الجامعي *", 
                key="reg_student_id", 
                placeholder="مثال: 4210380",
                help="الرقم الجامعي الخاص بك في نظام الليرناتا"
            )
            full_name = st.text_input(
                "الاسم الكامل *", 
                key="reg_student_full_name", 
                placeholder="مثال: أحمد محمد",
                help="اسمك الكامل"
            )
            email = st.text_input(
                "البريد الإلكتروني (اختياري)", 
                key="reg_student_email", 
                placeholder="example@university.edu",
                help="البريد الإلكتروني اختياري للطلاب"
            )
            password = st.text_input(
                "كلمة المرور (كلمة سر نظام الليرناتا) *", 
                type="password", 
                key="reg_student_password", 
                placeholder="كلمة مرور نظام الليرناتا",
                help="كلمة السر التي تستخدمها لتسجيل الدخول إلى نظام الليرناتا"
            )
            submitted = st.form_submit_button("📝 تسجيل كطالب", use_container_width=True, type="primary")
            
            if submitted:
                if not all([user_id, full_name, password]):
                    st.error("❌ يرجى ملء جميع الحقول المطلوبة (الرقم الجامعي، الاسم الكامل، كلمة المرور).")
                else:
                    register_data = {
                        "user_id": user_id,
                        "full_name": full_name,
                        "email": email if email and email.strip() else None,
                        "password": password
                    }
                    with st.spinner("⏳ جاري التحقق من بياناتك في النظام الجامعي..."):
                        response = post_request(f"{BACKEND_URL}/register/student", register_data)
                    
                    if response and response.get("user_id"):
                        st.success("✅ تم التسجيل بنجاح! يمكنك الآن تسجيل الدخول.")
                        st.balloons()
                    else:
                        st.error("❌ فشل التسجيل. تحقق من صحة الرقم الجامعي وكلمة المرور في نظام الليرناتا.")

    with tab3:
        st.subheader("👤 إنشاء حساب أدمن جديد")
        
        # التحقق من وجود أدمن موجود
        check_admin_endpoint = f"{BACKEND_URL}/users/me"
        has_existing_admin = False
        if st.session_state.logged_in and st.session_state.user_role == "admin":
            has_existing_admin = True
            st.warning("⚠️ **للمسؤولين فقط:** يمكنك إنشاء حسابات أدمن جديدة")
        else:
            st.info("💡 **إنشاء حساب أدمن أولي:** إذا لم يكن هناك أدمن موجود، يمكنك إنشاء حساب أدمن أولي")
        
        if not st.session_state.logged_in or st.session_state.user_role != "admin":
            st.warning("⚠️ **ملاحظة:** إذا كان هناك أدمن موجود بالفعل، يجب تسجيل الدخول كأدمن أولاً.")
        
        if True:  # السماح دائماً بمحاولة الإنشاء
            with st.form("register_admin_form"):
                user_id = st.text_input(
                    "معرف الأدمن *", 
                    key="reg_admin_id", 
                    placeholder="مثال: admin_001",
                    help="معرف فريد للأدمن"
                )
                full_name = st.text_input(
                    "الاسم الكامل *", 
                    key="reg_admin_full_name", 
                    placeholder="مثال: مدير النظام",
                    help="اسم الأدمن الكامل"
                )
                email = st.text_input(
                    "البريد الإلكتروني *", 
                    key="reg_admin_email", 
                    placeholder="admin@example.com",
                    help="البريد الإلكتروني مطلوب للأدمن"
                )
                password = st.text_input(
                    "كلمة المرور *", 
                    type="password", 
                    key="reg_admin_password", 
                    placeholder="كلمة مرور قوية (6 أحرف على الأقل)",
                    help="كلمة مرور قوية للأدمن"
                )
                submitted = st.form_submit_button("👤 إنشاء حساب أدمن", use_container_width=True, type="primary")
                
                if submitted:
                    if not all([user_id, full_name, email, password]) or len(password) < 6:
                        st.error("❌ يرجى ملء جميع الحقول المطلوبة. كلمة المرور يجب أن تكون 6 أحرف على الأقل.")
                    else:
                        register_data = {
                            "user_id": user_id,
                            "full_name": full_name,
                            "email": email,
                            "password": password
                        }
                        with st.spinner("⏳ جاري إنشاء حساب الأدمن..."):
                            # محاولة استخدام endpoint العادي أولاً (إذا كان المستخدم أدمن)
                            if st.session_state.logged_in and st.session_state.user_role == "admin":
                                headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
                                response = post_request(f"{BACKEND_URL}/register/admin", register_data, headers=headers)
                            else:
                                # استخدام endpoint إنشاء الأدمن الأولي
                                response = post_request(f"{BACKEND_URL}/register/admin/initial", register_data)
                        
                        if response and response.get("user_id"):
                            st.success("✅ تم إنشاء حساب الأدمن بنجاح! يمكنك الآن تسجيل الدخول.")
                            st.balloons()
                            st.info("💡 يمكنك الآن تسجيل الدخول باستخدام البريد الإلكتروني وكلمة المرور التي أدخلتها.")
                        else:
                            error_detail = response.get("detail", "فشل إنشاء حساب الأدمن") if response else "فشل الاتصال بالخادم"
                            st.error(f"❌ {error_detail}")
                            if "يوجد أدمن موجود" in str(error_detail):
                                st.info("💡 يجب تسجيل الدخول كأدمن موجود لإنشاء حسابات أدمن جديدة.")

# ------------------------------------------------------------
# واجهة دليل البيانات (Data Guide)
# ------------------------------------------------------------

def data_guide_interface():
    """واجهة دليل البيانات - توضح أين يجب تخزين البيانات والصيغ المقبولة."""
    st.header("📚 دليل البيانات")
    st.caption("تعرف على كيفية إضافة المستندات والبيانات إلى النظام")
    
    # معلومات عامة
    st.markdown("---")
    st.subheader("📍 موقع تخزين البيانات")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        st.info("""
        **في Docker:**
        - المسار: `/app/data`
        - داخل الحاوية: `backend:/app/data`
        """)
    with col2:
        st.info("""
        **محلياً (Local):**
        - المسار: `./data` (في مجلد المشروع)
        - مثال: `C:\\Projects\\my-ai-advisor\\data`
        """)
    
    st.markdown("---")
    st.subheader("📄 الصيغ المدعومة")
    
    # جدول الصيغ المدعومة
    formats_data = {
        "الصيغة": ["PDF", "DOCX", "DOC", "JPG/JPEG", "PNG", "TIFF", "TXT"],
        "الوصف": [
            "مستندات PDF (نص وصور)",
            "مستندات Word الحديثة",
            "مستندات Word القديمة",
            "صور JPEG",
            "صور PNG",
            "صور TIFF",
            "ملفات نصية عادية"
        ],
        "الامتداد": [".pdf", ".docx", ".doc", ".jpg, .jpeg", ".png", ".tiff", ".txt"],
        "ملاحظات": [
            "يدعم OCR للصور المضمنة",
            "✅ موصى به",
            "⚠️ قد لا يعمل بشكل مثالي",
            "يتطلب OCR",
            "يتطلب OCR",
            "يتطلب OCR",
            "✅ موصى به"
        ]
    }
    
    df_formats = pd.DataFrame(formats_data)
    st.dataframe(df_formats, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.subheader("📝 خطوات إضافة البيانات")
    
    steps = [
        "1. **ضع الملفات** في مجلد `data` (في المشروع المحلي أو داخل Docker)",
        "2. **تأكد من الصيغة** - استخدم الصيغ المدعومة أعلاه",
        "3. **سجل الدخول** كمسؤول (admin)",
        "4. **اضغط على زر** '📄 فهرسة المستندات (RAG)' في القائمة الجانبية",
        "5. **انتظر** حتى تكتمل عملية الفهرسة (قد تستغرق بضع دقائق)",
        "6. **استخدم الدردشة** لطرح الأسئلة على المستندات المفهرسة"
    ]
    
    for step in steps:
        st.markdown(f"- {step}")
    
    st.markdown("---")
    st.subheader("⚠️ ملاحظات مهمة")
    
    warnings = [
        "**حجم الملفات:** حاول ألا تتجاوز الملفات 50MB لكل ملف",
        "**عدد الملفات:** يمكن إضافة عدد غير محدود من الملفات",
        "**إعادة الفهرسة:** عند إضافة ملفات جديدة، يجب إعادة الفهرسة",
        "**اللغة:** النظام يدعم العربية والإنجليزية",
        "**الجداول:** يتم استخراج الجداول كنص عادي",
        "**الصور:** الصور المضمنة في PDF قد تحتاج OCR (قد لا يعمل دائماً)"
    ]
    
    for warning in warnings:
        st.markdown(f"- {warning}")
    
    st.markdown("---")
    st.subheader("🔍 مثال على البنية")
    
    st.code("""
my-ai-advisor/
├── data/
│   ├── اللائحة_الداخلية.pdf
│   ├── توصيف_المقررات.docx
│   ├── الخطة_الدراسية.pdf
│   └── ...
├── backend/
├── frontend/
└── docker-compose.yml
    """, language="text")

# ------------------------------------------------------------
# واجهة الإعدادات (Settings)
# ------------------------------------------------------------

def settings_interface():
    """واجهة الإعدادات - الوضع واللغة."""
    st.header("⚙️ الإعدادات")
    st.caption("قم بتخصيص مظهر وواجهة التطبيق")
    
    st.markdown("---")
    
    # الوضع النهاري/الليلي
    st.subheader("🌓 الوضع")
    theme_options = {
        "🌙 ليلي (Dark)": "dark",
        "☀️ نهاري (Light)": "light"
    }
    
    current_theme_label = [k for k, v in theme_options.items() if v == st.session_state.theme][0]
    new_theme_label = st.radio(
        "اختر الوضع:",
        options=list(theme_options.keys()),
        index=list(theme_options.keys()).index(current_theme_label),
        key="theme_selector"
    )
    
    if theme_options[new_theme_label] != st.session_state.theme:
        st.session_state.theme = theme_options[new_theme_label]
        st.rerun()
    
    st.markdown("---")
    
    # اللغة
    st.subheader("🌐 اللغة")
    language_options = {
        "العربية": "ar",
        "English": "en"
    }
    
    current_lang_label = [k for k, v in language_options.items() if v == st.session_state.language][0]
    new_lang_label = st.radio(
        "اختر اللغة:",
        options=list(language_options.keys()),
        index=list(language_options.keys()).index(current_lang_label),
        key="language_selector"
    )
    
    if language_options[new_lang_label] != st.session_state.language:
        st.session_state.language = language_options[new_lang_label]
        st.session_state.language_changed = True
        st.rerun()
    
    st.markdown("---")
    st.info("💡 التغييرات يتم تطبيقها فوراً. قد تحتاج إلى تحديث الصفحة لرؤية جميع التغييرات.")

# ------------------------------------------------------------
# التنقل بين الصفحات
# ------------------------------------------------------------

# ------------------------------------------------------------
# Advisor Dashboard Interface
# واجهة لوحة تحكم المرشد
# ------------------------------------------------------------

def advisor_dashboard_interface():
    """لوحة تحكم المرشد - مراجعة تنبيهات الطلاب واتخاذ التدخلات"""
    st.header("📋 لوحة تحكم المرشد الأكاديمي")
    st.caption("مراجعة تنبيهات الطلاب واتخاذ التدخلات المناسبة")
    
    if st.session_state.user_role not in ["admin", "advisor"]:
        st.error("⚠️ هذه الصفحة متاحة فقط للمرشدين والإداريين")
        return
    
    headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
    
    # Filters
    col1, col2 = st.columns(2)
    with col1:
        priority_filter = st.selectbox(
            "تصفية حسب الأولوية",
            ["all", "critical", "high", "medium", "low"],
            key="advisor_priority_filter"
        )
    with col2:
        limit = st.number_input("عدد التنبيهات", min_value=10, max_value=100, value=50, step=10)
    
    # Fetch alerts
    if st.button("🔄 تحديث التنبيهات", use_container_width=True):
        params = {"limit": limit}
        if priority_filter != "all":
            params["priority"] = priority_filter
        
        alerts = get_request(
            f"{BACKEND_URL}/advisor/alerts/pending",
            headers=headers
        )
        
        if alerts:
            st.session_state.advisor_alerts = alerts
        else:
            st.session_state.advisor_alerts = []
    
    # Display alerts
    if "advisor_alerts" in st.session_state and st.session_state.advisor_alerts:
        alerts = st.session_state.advisor_alerts
        
        st.metric("عدد التنبيهات المعلّقة", len(alerts))
        
        for alert in alerts:
            with st.expander(f"🔴 {alert.get('student_id', 'Unknown')} - {alert.get('risk_level', 'unknown').upper()}", expanded=True):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"**الوصف:** {alert.get('description', 'N/A')}")
                    
                    # Contributing factors
                    if alert.get('contributing_factors'):
                        st.subheader("العوامل المساهمة:")
                        factors = alert.get('contributing_factors', {})
                        for factor, importance in sorted(factors.items(), key=lambda x: x[1], reverse=True)[:3]:
                            st.progress(importance, text=f"{factor}: {importance*100:.1f}%")
                    
                    st.caption(f"دقة التنبؤ: {alert.get('prediction_confidence', 0)*100:.1f}%")
                
                with col2:
                    st.selectbox(
                        "الإجراء",
                        ["email", "meeting", "resource_suggestion", "dismiss"],
                        key=f"action_{alert['id']}"
                    )
                    
                    notes = st.text_area("ملاحظات", key=f"notes_{alert['id']}", height=100)
                    
                    if st.button("💾 حفظ الإجراء", key=f"save_{alert['id']}"):
                        action_data = {
                            "action_type": st.session_state.get(f"action_{alert['id']}", "email"),
                            "notes": notes
                        }
                        
                        result = post_request(
                            f"{BACKEND_URL}/advisor/alerts/{alert['id']}/action",
                            action_data,
                            headers=headers
                        )
                        
                        if result:
                            st.success("✅ تم حفظ الإجراء بنجاح")
                            st.rerun()
    else:
        st.info("لا توجد تنبيهات معلّقة حالياً")

# ------------------------------------------------------------
# Wellness Monitor Interface
# واجهة مراقب العافية
# ------------------------------------------------------------

def wellness_monitor_interface():
    """واجهة مراقبة العافية للطلاب"""
    st.header("💚 مراقب العافية الاستباقي")
    st.caption("تحليل أنماط التفاعل للكشف المبكر عن علامات الإرهاق الأكاديمي")
    
    headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
    
    # Student selection (for advisors/admins)
    student_id = None
    if st.session_state.user_role in ["admin", "advisor"]:
        student_id = st.text_input("معرف الطالب", key="wellness_student_id")
    else:
        student_id = st.session_state.user_id
    
    if not student_id:
        st.warning("⚠️ يرجى إدخال معرف الطالب")
        return
    
    col1, col2 = st.columns(2)
    with col1:
        days_window = st.number_input("نافذة التحليل (أيام)", min_value=7, max_value=30, value=14)
    
    if st.button("🔍 تحليل العافية", use_container_width=True):
        wellness_data = get_request(
            f"{BACKEND_URL}/wellness/students/{student_id}?days_window={days_window}",
            headers=headers
        )
        
        if wellness_data:
            st.session_state.wellness_data = wellness_data
    
    # Display wellness analysis
    if "wellness_data" in st.session_state and st.session_state.wellness_data:
        data = st.session_state.wellness_data
        
        if data.get("opt_in_required"):
            st.warning("⚠️ الطالب لم يوافق على مراقبة العافية")
            if st.button("📝 طلب الموافقة"):
                st.info("سيتم إرسال طلب موافقة للطالب")
            return
        
        # Wellness Score Gauge
        wellness_score = data.get("wellness_score", 0)
        alert_level = data.get("alert_level", "green")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("مؤشر العافية", f"{wellness_score*100:.0f}%")
        
        with col2:
            color_map = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
            st.metric("مستوى التنبيه", f"{color_map.get(alert_level, '⚪')} {alert_level}")
        
        with col3:
            deviations_count = len(data.get("deviations", []))
            st.metric("الانحرافات المكتشفة", deviations_count)
        
        # Progress bar for wellness score
        st.progress(wellness_score, text=f"مؤشر العافية: {wellness_score*100:.0f}%")
        
        # Indicators
        st.subheader("📊 المؤشرات السلوكية")
        indicators = data.get("indicators", {})
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("نمط التسليم", f"{indicators.get('submission_pattern', 'N/A')}")
            st.metric("مدة الجلسة (دقيقة)", f"{indicators.get('session_duration_avg', 'N/A')}")
        
        with col2:
            st.metric("التفاعل الاجتماعي", f"{indicators.get('social_engagement', 0)}")
            st.metric("النشاط الليلي", f"{indicators.get('late_night_activity', 0)}")
        
        # Deviations
        deviations = data.get("deviations", [])
        if deviations:
            st.subheader("⚠️ الانحرافات المكتشفة")
            for dev in deviations:
                st.warning(f"**{dev.get('type', 'Unknown')}**: {dev.get('description', 'N/A')}")
        
        # Recommended Intervention
        intervention = data.get("recommended_intervention")
        if intervention:
            st.subheader("💡 التوصية")
            st.info(intervention)
            
            if st.button("📞 طلب المساعدة من المرشد"):
                st.success("✅ تم إرسال طلب المساعدة")

# ------------------------------------------------------------
# Peer Matching Interface
# واجهة مطابقة الأقران
# ------------------------------------------------------------

def peer_matching_interface():
    """واجهة مطابقة الأقران للعثور على شركاء دراسة"""
    st.header("🤝 العثور على شركاء دراسة")
    st.caption("مطابقة ذكية بناءً على أسلوب التعلم والأداء الأكاديمي")
    
    headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
    
    student_id = st.session_state.user_id
    
    col1, col2 = st.columns(2)
    with col1:
        course_code = st.text_input("رمز المقرر (اختياري)", key="peer_course_code")
    with col2:
        match_type = st.selectbox(
            "نوع المطابقة",
            ["homogeneous", "heterogeneous"],
            format_func=lambda x: "متشابهون (للمراجعة)" if x == "homogeneous" else "متكاملون (للمشاريع)",
            key="peer_match_type"
        )
    
    max_matches = st.number_input("عدد المطابقات", min_value=1, max_value=20, value=5)
    
    if st.button("🔍 البحث عن شركاء", use_container_width=True):
        params = {
            "student_id": student_id,
            "match_type": match_type,
            "max_matches": max_matches
        }
        if course_code:
            params["course_code"] = course_code
        
        matches = get_request(
            f"{BACKEND_URL}/peer-matching/find",
            headers=headers
        )
        
        if matches:
            st.session_state.peer_matches = matches
        else:
            st.session_state.peer_matches = []
    
    # Display matches
    if "peer_matches" in st.session_state and st.session_state.peer_matches:
        matches = st.session_state.peer_matches
        
        st.success(f"✅ تم العثور على {len(matches)} مطابقة")
        
        for match in matches:
            with st.container():
                col1, col2 = st.columns([1, 3])
                
                with col1:
                    score = match.get("compatibility_score", 0)
                    st.metric("التوافق", f"{score*100:.0f}%")
                    st.progress(score)
                
                with col2:
                    st.markdown(f"### {match.get('student_name', 'Unknown')}")
                    st.markdown(f"**السبب:** {match.get('match_reason', 'N/A')}")
                    
                    # Learning style badges
                    style = match.get("learning_style", {})
                    if style:
                        cols = st.columns(4)
                        for idx, (dim, value) in enumerate(style.items()):
                            if idx < 4:
                                cols[idx].badge(value)
                    
                    if st.button(f"📧 إرسال طلب تواصل", key=f"contact_{match.get('student_id')}"):
                        st.info("سيتم إرسال طلب التواصل للطالب")

# ------------------------------------------------------------
# Admin Bulk Import Interface
# واجهة استيراد الطلاب بالجملة
# ------------------------------------------------------------

def admin_bulk_import_interface():
    """واجهة استيراد الطلاب بالجملة من CSV"""
    st.header("📥 استيراد الطلاب بالجملة (CSV)")
    st.caption("استيراد 3500+ طالب من ملفات CSV متعددة")
    
    if st.session_state.user_role != "admin":
        st.error("⚠️ هذه الصفحة متاحة فقط للإداريين")
        return
    
    headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
    
    st.info("""
    **تعليمات الاستيراد:**
    - كل طالب له ملف CSV خاص به
    - يجب أن يحتوي الملف على: student_id, name, email, major, courses, grades
    - ضع جميع ملفات CSV في مجلد واحد
    """)
    
    csv_folder_path = st.text_input(
        "مسار مجلد CSV",
        placeholder="C:/Projects/IntelliPath_Project/students",
        key="csv_folder_path"
    )
    
    batch_size = st.number_input("حجم الدفعة", min_value=10, max_value=500, value=100)
    
    if st.button("🚀 بدء الاستيراد", use_container_width=True, type="primary"):
        if not csv_folder_path:
            st.error("⚠️ يرجى إدخال مسار المجلد")
            return
        
        with st.spinner("⏳ جاري الاستيراد... قد يستغرق هذا وقتاً طويلاً"):
            import_data = {
                "csv_folder_path": csv_folder_path,
                "batch_size": batch_size
            }
            
            result = post_request(
                f"{BACKEND_URL}/admin/students/bulk-import",
                import_data,
                headers=headers,
                timeout=600  # 10 minutes timeout
            )
            
            if result:
                st.session_state.import_result = result
    
    # Display results
    if "import_result" in st.session_state and st.session_state.import_result:
        result = st.session_state.import_result
        
        col1, col2, col3 = st.columns(3)
        col1.metric("إجمالي الملفات", result.get("total_files", 0))
        col2.metric("✅ تم الاستيراد", result.get("imported", 0), delta=f"+{result.get('imported', 0)}")
        col3.metric("❌ فشل", result.get("failed", 0), delta=f"-{result.get('failed', 0)}", delta_color="inverse")
        
        # Errors
        errors = result.get("errors", [])
        if errors:
            with st.expander(f"⚠️ الأخطاء ({len(errors)})", expanded=False):
                for err in errors[:50]:  # Show first 50 errors
                    st.error(f"**{err.get('file', 'Unknown')}**: {err.get('error', 'Unknown error')}")

# تعريف الصفحات حسب الدور
STUDENT_PAGES = {
    "💬 الدردشة الذكية": chat_interface,
    "🔄 جمع البيانات": sync_data_interface,
    "📊 تحليل التقدم": progress_analysis_interface,
    "🧮 محاكي المعدل": gpa_simulator_interface,
    "💚 مراقب العافية": wellness_monitor_interface,
    "🤝 مطابقة الأقران": peer_matching_interface,
    "🔔 الإشعارات": notifications_interface,
    "🌳 الرسم البياني للمهارات": graph_interface,
    "📚 دليل البيانات": data_guide_interface,
    "⚙️ الإعدادات": settings_interface,
}

ADMIN_PAGES = {
    "💬 الدردشة الذكية": chat_interface,
    "📋 لوحة تحكم المرشد": advisor_dashboard_interface,
    "💚 مراقب العافية": wellness_monitor_interface,
    "📥 استيراد الطلاب": admin_bulk_import_interface,
    "📊 تحليل التقدم": progress_analysis_interface,
    "🧮 محاكي المعدل": gpa_simulator_interface,
    "🔔 الإشعارات": notifications_interface,
    "🌳 الرسم البياني للمهارات": graph_interface,
    "📚 دليل البيانات": data_guide_interface,
    "⚙️ الإعدادات": settings_interface,
}

# دالة للحصول على الصفحات حسب الدور
def get_pages_by_role(role: str) -> Dict[str, Any]:
    """الحصول على الصفحات المتاحة حسب دور المستخدم."""
    if role == "admin":
        return ADMIN_PAGES
    else:
        return STUDENT_PAGES

if st.session_state.logged_in:
    # Sidebar معلومات المستخدم
    st.sidebar.markdown("---")
    is_demo = st.session_state.user_id.startswith("demo_") if st.session_state.user_id else False
    if is_demo:
        st.sidebar.warning("⚠️ **وضع تجريبي**")
    st.sidebar.markdown(f"### 👤 {st.session_state.user_id}")
    st.sidebar.caption(f"الدور: **{st.session_state.user_role}**")
    
    # إعدادات سريعة في Sidebar
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ إعدادات سريعة")
    
    # تبديل الوضع
    theme_icon = "☀️" if st.session_state.theme == "dark" else "🌙"
    theme_text = "نهاري" if st.session_state.theme == "dark" else "ليلي"
    if st.sidebar.button(f"{theme_icon} {theme_text}", use_container_width=True, key="theme_toggle"):
        # تغيير الوضع
        st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"
        st.rerun()
    
    # تبديل اللغة
    lang_text = "English" if st.session_state.language == "ar" else "العربية"
    if st.sidebar.button(f"🌐 {lang_text}", use_container_width=True, key="lang_toggle"):
        # تغيير اللغة
        st.session_state.language = "en" if st.session_state.language == "ar" else "ar"
        st.session_state.language_changed = True
        st.rerun()
    
    st.sidebar.markdown("---")
    
    if st.sidebar.button("🚪 تسجيل الخروج", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.access_token = None
        st.session_state.user_id = None
        st.session_state.user_role = None
        st.session_state.messages = []
        st.rerun()
    
    st.sidebar.markdown("---")
    
    # الحصول على الصفحات المتاحة حسب الدور
    available_pages = get_pages_by_role(st.session_state.user_role)
    selection = st.sidebar.radio("📋 اختر الخدمة", list(available_pages.keys()))

    # عرض وظيفة الإعداد الأولي (فقط للأدمن)
    if st.session_state.user_role == "admin":
        setup_initial_data()

    # عرض الصفحة المختارة
    page = available_pages[selection]
    page()
else:
    login_interface()
