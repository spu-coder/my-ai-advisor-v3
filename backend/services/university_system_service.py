import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from bs4 import BeautifulSoup
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import re
import urllib3

logger = logging.getLogger("UNIVERSITY_SYSTEM_SERVICE")

# رابط النظام الجامعي
UNIVERSITY_BASE_URL = "https://my.spu.edu.sy"
LOGIN_URL = f"{UNIVERSITY_BASE_URL}/login"

# تحسين User-Agent ليكون أكثر واقعية
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

VERIFY_SSL_ENV = os.getenv("VERIFY_UNIVERSITY_SSL", "true").lower() in ("1", "true", "yes")

class UniversitySystemService:
    """خدمة للتفاعل مع النظام الجامعي وجمع بيانات الطالب."""
    
    def __init__(self):
        self.session = requests.Session()
        self.verify_ssl = VERIFY_SSL_ENV
        self.session.verify = self.verify_ssl

        if not self.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        self.session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        })
        self.logged_in = False
        self._login_retry_count = 0  # لتجنب infinite recursion
    
    def login(self, student_id: str, password: str) -> bool:
        """
        تسجيل الدخول إلى النظام الجامعي.
        
        Args:
            student_id: الرقم الجامعي
            password: كلمة السر
            
        Returns:
            True إذا نجح تسجيل الدخول، False خلاف ذلك
        """
        try:
            logger.info(f"محاولة تسجيل الدخول للطالب: {student_id}")
            
            # زيارة الصفحة الرئيسية أولاً لتوليد ملفات تعريف الارتباط الأساسية
            try:
                self.session.get(UNIVERSITY_BASE_URL, timeout=20)
            except Exception as warmup_error:
                logger.debug(f"Warm-up request failed: {warmup_error}")

            # الحصول على صفحة تسجيل الدخول للحصول على CSRF token إذا كان موجوداً
            login_page = self.session.get(LOGIN_URL, timeout=30)
            login_page.raise_for_status()
            
            soup = BeautifulSoup(login_page.text, 'html.parser')
            
            # حفظ HTML للتشخيص
            logger.debug(f"صفحة تسجيل الدخول - URL: {login_page.url}, Status: {login_page.status_code}")
            
            # البحث عن حقول النموذج بشكل دقيق
            form_data = {}
            
            # البحث عن CSRF token بطرق متعددة
            csrf_token = None
            
            # 1. البحث في meta tags
            csrf_meta = soup.find('meta', {'name': 'csrf-token'})
            if csrf_meta:
                csrf_token = csrf_meta.get('content')
                logger.info(f"تم العثور على CSRF token من meta tag: {csrf_token[:20]}...")
            
            # 2. البحث في input hidden
            if not csrf_token:
                hidden_inputs = soup.find_all('input', type='hidden')
                logger.debug(f"تم العثور على {len(hidden_inputs)} حقول hidden")
                for input_field in hidden_inputs:
                    name = input_field.get('name', '').lower()
                    value = input_field.get('value', '')
                    if name and ('csrf' in name or 'token' in name or '_token' in name):
                        csrf_token = value
                        logger.info(f"تم العثور على CSRF token من input: {name} = {csrf_token[:20]}...")
                        break
                    # إضافة جميع حقول hidden
                    if name:
                        form_data[name] = value
                        logger.debug(f"حقل hidden: {name} = {value[:20]}...")
            
            # 3. البحث في JavaScript (Laravel عادة يضع token في window.Laravel)
            if not csrf_token:
                scripts = soup.find_all('script')
                for script in scripts:
                    if script.string:
                        # البحث عن Laravel.csrfToken أو window.Laravel
                        token_match = re.search(r'(?:Laravel|window\.Laravel)\.csrfToken\s*[=:]\s*["\']([^"\']+)["\']', script.string)
                        if token_match:
                            csrf_token = token_match.group(1)
                            logger.info(f"تم العثور على CSRF token من JavaScript: {csrf_token[:20]}...")
                            break
            
            # 4. البحث عن _token في جميع حقول input
            if not csrf_token:
                token_input = soup.find('input', {'name': '_token'})
                if token_input:
                    csrf_token = token_input.get('value', '')
                    logger.info(f"تم العثور على _token: {csrf_token[:20]}...")
            
            # إضافة CSRF token إذا تم العثور عليه
            if csrf_token:
                form_data['_token'] = csrf_token
                logger.info(f"✅ تم إضافة CSRF token إلى النموذج")
            else:
                logger.warning(f"⚠️ لم يتم العثور على CSRF token - سيتم المحاولة بدون token")
            
            # البحث عن جميع حقول input hidden الأخرى
            hidden_inputs = soup.find_all('input', type='hidden')
            for input_field in hidden_inputs:
                name = input_field.get('name')
                value = input_field.get('value', '')
                if name and name not in form_data:
                    form_data[name] = value
                    logger.debug(f"حقل hidden: {name} = {value[:20]}...")
            
            # البحث عن جميع حقول input في النموذج
            all_inputs = soup.find_all('input')
            logger.debug(f"تم العثور على {len(all_inputs)} حقول input إجمالاً")
            
            # البحث عن حقل اسم المستخدم/الرقم الجامعي
            username_field = None
            possible_username_fields = [
                'username', 'user', 'student_id', 'student_number', 
                'studentId', 'studentNumber', 'رقم_جامعي', 'email',
                'login', 'user_name', 'userName'
            ]
            
            # البحث في جميع حقول input
            for input_field in all_inputs:
                field_name = input_field.get('name') or input_field.get('id', '')
                field_type = input_field.get('type', '')
                
                # تخطي حقول password و hidden
                if field_type in ['password', 'hidden', 'submit', 'button']:
                    continue
                
                # البحث عن حقل اسم المستخدم
                if field_name.lower() in [f.lower() for f in possible_username_fields]:
                    username_field = field_name
                    logger.info(f"تم العثور على حقل اسم المستخدم: {username_field}")
                    break
                
                # إذا كان الحقل text وليس password، قد يكون حقل اسم المستخدم
                if field_type == 'text' and not username_field:
                    # محاولة تحديد الحقل من الـ label أو placeholder
                    label = soup.find('label', {'for': input_field.get('id', '')})
                    if label:
                        label_text = label.get_text(strip=True).lower()
                        if any(keyword in label_text for keyword in ['username', 'user', 'student', 'رقم', 'جامعي', 'email']):
                            username_field = field_name
                            logger.info(f"تم تحديد حقل اسم المستخدم من الـ label: {username_field}")
                            break
            
            # إذا لم نجد حقل محدد، نبحث عن أول حقل text
            if not username_field:
                for input_field in all_inputs:
                    if input_field.get('type') == 'text':
                        username_field = input_field.get('name') or input_field.get('id', '')
                        if username_field:
                            logger.warning(f"استخدام حقل text افتراضي: {username_field}")
                            break
            
            # إذا لم نجد أي حقل، نستخدم 'username' كافتراضي
            if not username_field:
                username_field = 'username'
                logger.warning(f"استخدام 'username' كافتراضي")
            
            form_data[username_field] = student_id
            form_data['password'] = password
            
            logger.info(f"إرسال بيانات تسجيل الدخول - الحقل: {username_field}, الرقم: {student_id}")
            logger.debug(f"بيانات النموذج: {list(form_data.keys())}")
            
            # إضافة headers إضافية لتحسين التوافق
            headers = {
                'Referer': LOGIN_URL,
                'Origin': UNIVERSITY_BASE_URL,
                'X-Requested-With': 'XMLHttpRequest'  # بعض الأنظمة تفضل هذا
            }
            
            # إرسال طلب تسجيل الدخول
            response = self.session.post(LOGIN_URL, data=form_data, headers=headers, timeout=30, allow_redirects=True)
            
            logger.info(f"استجابة تسجيل الدخول - Status: {response.status_code}, URL: {response.url}")
            
            # معالجة HTTP 419 (CSRF token expired)
            if response.status_code == 419:
                if self._login_retry_count < 1:  # محاولة واحدة فقط
                    logger.warning(f"⚠️ HTTP 419 - CSRF token expired, محاولة إعادة الحصول على token...")
                    self._login_retry_count += 1
                    # إعادة تهيئة الجلسة للحصول على token جديد
                    self.session.close()
                    self.session = requests.Session()
                    self.session.verify = self.verify_ssl
                    if not self.verify_ssl:
                        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                    self.session.headers.update({
                        'User-Agent': USER_AGENT,
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                        'Cache-Control': 'max-age=0'
                    })
                    # إعادة المحاولة مع token جديد
                    return self.login(student_id, password)
                else:
                    logger.error(f"❌ فشل تسجيل الدخول بعد محاولة إعادة: HTTP 419")
                    return False
            
            # التحقق من نجاح تسجيل الدخول
            if response.status_code in [200, 302]:
                # التحقق من أننا لم نعد في صفحة تسجيل الدخول
                current_url = response.url.lower()
                
                # إذا تم إعادة التوجيه إلى صفحة أخرى (ليس login)
                if 'login' not in current_url:
                    self.logged_in = True
                    logger.info(f"✅ تم تسجيل الدخول بنجاح للطالب: {student_id}")
                    return True
                
                # إذا كنا لا نزال في صفحة login، نفحص وجود رسائل خطأ
                soup_response = BeautifulSoup(response.text, 'html.parser')
                
                # البحث عن رسائل الخطأ بطرق مختلفة
                error_selectors = [
                    {'class': re.compile(r'error|alert|danger', re.I)},
                    {'id': re.compile(r'error|alert|danger', re.I)},
                    {'role': 'alert'},
                ]
                
                error_messages = []
                for selector in error_selectors:
                    errors = soup_response.find_all(['div', 'span', 'p', 'li'], selector)
                    error_messages.extend([msg.get_text(strip=True) for msg in errors])
                
                # البحث عن رسائل خطأ في النص
                page_text = soup_response.get_text().lower()
                error_keywords = ['خطأ', 'error', 'فشل', 'failed', 'غير صحيح', 'incorrect', 'invalid', '419']
                if any(keyword in page_text for keyword in error_keywords):
                    # محاولة استخراج رسالة الخطأ
                    for keyword in error_keywords:
                        if keyword in page_text:
                            error_messages.append(f"رسالة خطأ تحتوي على: {keyword}")
                
                if error_messages:
                    error_text = ' | '.join(error_messages[:3])  # أول 3 رسائل
                    logger.warning(f"❌ فشل تسجيل الدخول: {error_text}")
                else:
                    logger.warning(f"❌ فشل تسجيل الدخول: لا يمكن التحقق من نجاح العملية (URL: {current_url})")
                
                return False
            else:
                error_msg = f"❌ خطأ في تسجيل الدخول: HTTP {response.status_code}"
                if response.status_code == 419:
                    error_msg += " (CSRF token expired or missing)"
                logger.error(error_msg)
                return False
                
        except requests.exceptions.Timeout:
            logger.error(f"⏱️ انتهت مهلة الاتصال بالنظام الجامعي")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ خطأ في الاتصال بالنظام الجامعي: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"❌ خطأ غير متوقع في تسجيل الدخول: {str(e)}", exc_info=True)
            return False
    
    def get_grades_status(self) -> Optional[Dict[str, Any]]:
        """جلب حالة الدرجات من صفحة حالة الدرجات."""
        if not self.logged_in:
            logger.error("يجب تسجيل الدخول أولاً")
            return None
        
        try:
            url = f"{UNIVERSITY_BASE_URL}/students/grades/status"
            logger.info(f"جلب حالة الدرجات من: {url}")
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            page_text = soup.get_text()
            
            logger.debug(f"حالة الدرجات - Status: {response.status_code}, URL: {response.url}")
            logger.debug(f"طول النص: {len(page_text)} حرف")
            
            # استخراج البيانات من الصفحة
            data = {
                'gpa': None,
                'total_hours': None,
                'completed_hours': None,
                'remaining_hours': None,
                'status': None,
                'raw_html': response.text[:2000]  # حفظ جزء من HTML للتشخيص
            }
            
            # البحث عن المعدل التراكمي بطرق متعددة
            gpa_patterns = [
                r'المعدل\s*التراكمي[:\s]*([\d.]+)',
                r'GPA[:\s]*([\d.]+)',
                r'معدل[:\s]*([\d.]+)',
                r'المعدل[:\s]*([\d.]+)',
                r'gpa[:\s]*([\d.]+)',
                r'(\d+\.\d+)\s*\(?gpa\)?',
            ]
            
            # البحث في النص
            for pattern in gpa_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    try:
                        gpa_value = float(match.group(1))
                        if 0 <= gpa_value <= 4.0:  # التحقق من أن المعدل منطقي
                            data['gpa'] = gpa_value
                            logger.info(f"✅ تم العثور على المعدل التراكمي: {gpa_value}")
                            break
                    except ValueError:
                        continue
            
            # البحث في الجداول
            if not data['gpa']:
                tables = soup.find_all('table')
                for table in tables:
                    rows = table.find_all('tr')
                    for row in rows:
                        cells = [cell.get_text(strip=True) for cell in row.find_all(['td', 'th'])]
                        for i, cell in enumerate(cells):
                            if any(keyword in cell.lower() for keyword in ['معدل', 'gpa', 'تراكمي']):
                                if i + 1 < len(cells):
                                    try:
                                        gpa_value = float(re.search(r'[\d.]+', cells[i+1]).group())
                                        if 0 <= gpa_value <= 4.0:
                                            data['gpa'] = gpa_value
                                            logger.info(f"✅ تم العثور على المعدل من الجدول: {gpa_value}")
                                            break
                                    except:
                                        pass
            
            # البحث عن الساعات بطرق متعددة
            hours_patterns = [
                r'الساعات\s*المكتملة[:\s]*(\d+)',
                r'إجمالي\s*الساعات[:\s]*(\d+)',
                r'ساعات\s*مكتملة[:\s]*(\d+)',
                r'المكتملة[:\s]*(\d+)',
                r'completed\s*hours[:\s]*(\d+)',
                r'total\s*hours[:\s]*(\d+)',
            ]
            
            for pattern in hours_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    try:
                        hours_value = int(match.group(1))
                        if 0 <= hours_value <= 200:  # التحقق من أن الساعات منطقية
                            data['completed_hours'] = hours_value
                            logger.info(f"✅ تم العثور على الساعات المكتملة: {hours_value}")
                            break
                    except ValueError:
                        continue
            
            # البحث في الجداول للساعات
            if not data['completed_hours']:
                tables = soup.find_all('table')
                for table in tables:
                    rows = table.find_all('tr')
                    for row in rows:
                        cells = [cell.get_text(strip=True) for cell in row.find_all(['td', 'th'])]
                        for i, cell in enumerate(cells):
                            if any(keyword in cell.lower() for keyword in ['ساعات', 'hours', 'مكتملة']):
                                if i + 1 < len(cells):
                                    try:
                                        hours_value = int(re.search(r'\d+', cells[i+1]).group())
                                        if 0 <= hours_value <= 200:
                                            data['completed_hours'] = hours_value
                                            logger.info(f"✅ تم العثور على الساعات من الجدول: {hours_value}")
                                            break
                                    except:
                                        pass
            
            logger.info(f"نتائج حالة الدرجات: GPA={data['gpa']}, Hours={data['completed_hours']}")
            return data
            
        except Exception as e:
            logger.error(f"❌ خطأ في جلب حالة الدرجات: {str(e)}", exc_info=True)
            return None
    
    def get_current_semester_transcript(self) -> Optional[List[Dict[str, Any]]]:
        """جلب كشف درجات الفصل الحالي."""
        if not self.logged_in:
            logger.error("يجب تسجيل الدخول أولاً")
            return None
        
        try:
            url = f"{UNIVERSITY_BASE_URL}/students/grades/transcript-current-semester"
            logger.info(f"جلب كشف درجات الفصل الحالي من: {url}")
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            logger.debug(f"كشف الفصل الحالي - Status: {response.status_code}, URL: {response.url}")
            
            courses = []
            tables = soup.find_all('table')
            logger.debug(f"تم العثور على {len(tables)} جدول")
            
            for table_idx, table in enumerate(tables):
                rows = table.find_all('tr')
                if not rows:
                    continue
                
                # الحصول على رؤوس الأعمدة
                header_row = rows[0]
                headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
                logger.debug(f"جدول {table_idx + 1} - الرؤوس: {headers}")
                
                # معالجة صفوف البيانات
                for row_idx, row in enumerate(rows[1:], 1):
                    cells = row.find_all(['td', 'th'])
                    if len(cells) < 2:  # على الأقل عمودين
                        continue
                    
                    course_data = {}
                    for i, cell in enumerate(cells):
                        header = headers[i] if i < len(headers) else f"column_{i}"
                        value = cell.get_text(strip=True)
                        course_data[header] = value
                    
                    # محاولة استخراج معلومات المقرر بشكل منظم
                    # البحث عن رمز المقرر
                    course_code = None
                    course_name = None
                    grade = None
                    hours = None
                    
                    # البحث في جميع الأعمدة
                    for key, value in course_data.items():
                        key_lower = key.lower()
                        value_clean = value.strip()
                        
                        # البحث عن رمز المقرر
                        if not course_code:
                            if any(kw in key_lower for kw in ['رمز', 'code', 'مقرر', 'course']):
                                course_code = value_clean
                            elif re.match(r'^[A-Z]{2,4}\d{3,4}$', value_clean):  # نمط مثل CS101, MATH202
                                course_code = value_clean
                        
                        # البحث عن اسم المقرر
                        if not course_name:
                            if any(kw in key_lower for kw in ['اسم', 'name', 'عنوان', 'title']):
                                course_name = value_clean
                        
                        # البحث عن الدرجة
                        if not grade:
                            if any(kw in key_lower for kw in ['درجة', 'grade', 'علامة', 'mark', 'score']):
                                grade = value_clean
                            elif re.match(r'^[A-F][+-]?$', value_clean.upper()):  # نمط مثل A, B+, C-
                                grade = value_clean.upper()
                        
                        # البحث عن الساعات
                        if not hours:
                            if any(kw in key_lower for kw in ['ساعات', 'hours', 'ساعة', 'hour', 'credit']):
                                try:
                                    hours = int(re.search(r'\d+', value_clean).group())
                                except:
                                    pass
                    
                    # إذا وجدنا على الأقل رمز المقرر أو اسمه، نضيفه
                    if course_code or course_name or any(v.strip() for v in course_data.values() if v):
                        course_info = {
                            'course_code': course_code or f"COURSE_{len(courses) + 1}",
                            'course_name': course_name,
                            'grade': grade,
                            'hours': hours,
                            'raw_data': course_data
                        }
                        courses.append(course_info)
                        logger.debug(f"مقرر {len(courses)}: {course_code} - {course_name} - {grade} - {hours} ساعة")
            
            logger.info(f"✅ تم جمع {len(courses)} مقرر من الفصل الحالي")
            return courses
            
        except Exception as e:
            logger.error(f"❌ خطأ في جلب كشف درجات الفصل الحالي: {str(e)}", exc_info=True)
            return None
    
    def get_all_semesters_transcript(self) -> Optional[Dict[str, List[Dict[str, Any]]]]:
        """جلب كشف درجات جميع الفصول الدراسية."""
        if not self.logged_in:
            logger.error("يجب تسجيل الدخول أولاً")
            return None
        
        try:
            url = f"{UNIVERSITY_BASE_URL}/students/grades/transcript-semesters"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # تجميع البيانات حسب الفصل الدراسي
            semesters_data = {}
            
            # البحث عن جداول أو أقسام لكل فصل
            # قد تكون منظمة كأقسام div أو جداول منفصلة
            semester_sections = soup.find_all(['div', 'section'], class_=re.compile(r'semester|فصل', re.I))
            
            if not semester_sections:
                # إذا لم نجد أقسام، نبحث عن جميع الجداول
                tables = soup.find_all('table')
                semester_sections = tables
            
            for section in semester_sections:
                semester_name = None
                
                # محاولة تحديد اسم الفصل
                semester_header = section.find(['h2', 'h3', 'h4', 'strong', 'b'])
                if semester_header:
                    semester_name = semester_header.get_text(strip=True)
                
                if not semester_name:
                    semester_name = f"semester_{len(semesters_data) + 1}"
                
                # استخراج المقررات من هذا الفصل
                courses = []
                table = section.find('table') if section.name != 'table' else section
                
                if table:
                    rows = table.find_all('tr')
                    if rows:
                        headers = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])]
                        
                        for row in rows[1:]:
                            cells = row.find_all(['td', 'th'])
                            if len(cells) >= 3:
                                course_data = {}
                                for i, cell in enumerate(cells):
                                    header = headers[i] if i < len(headers) else f"column_{i}"
                                    course_data[header] = cell.get_text(strip=True)
                                courses.append(course_data)
                
                if courses:
                    semesters_data[semester_name] = courses
            
            return semesters_data
            
        except Exception as e:
            logger.error(f"خطأ في جلب كشف درجات جميع الفصول: {str(e)}")
            return None
    
    def get_remaining_courses(self) -> Optional[List[Dict[str, Any]]]:
        """جلب المقررات المتبقية للتسجيل."""
        if not self.logged_in:
            logger.error("يجب تسجيل الدخول أولاً")
            return None
        
        try:
            url = f"{UNIVERSITY_BASE_URL}/students/registration/remaining-courses"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            courses = []
            tables = soup.find_all('table')
            
            for table in tables:
                rows = table.find_all('tr')
                if rows:
                    headers = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])]
                    
                    for row in rows[1:]:
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 2:
                            course_data = {}
                            for i, cell in enumerate(cells):
                                header = headers[i] if i < len(headers) else f"column_{i}"
                                course_data[header] = cell.get_text(strip=True)
                            courses.append(course_data)
            
            return courses
            
        except Exception as e:
            logger.error(f"خطأ في جلب المقررات المتبقية: {str(e)}")
            return None
    
    def collect_all_student_data(self, student_id: str, password: str) -> Dict[str, Any]:
        """
        جمع جميع بيانات الطالب من النظام الجامعي.
        
        Args:
            student_id: الرقم الجامعي
            password: كلمة السر
            
        Returns:
            قاموس يحتوي على جميع البيانات المجمعة
        """
        result = {
            'success': False,
            'student_id': student_id,
            'login_success': False,
            'grades_status': None,
            'current_semester_transcript': None,
            'all_semesters_transcript': None,
            'remaining_courses': None,
            'error': None
        }
        
        # تسجيل الدخول
        if not self.login(student_id, password):
            result['error'] = "فشل تسجيل الدخول إلى النظام الجامعي"
            return result
        
        result['login_success'] = True
        
        # جمع البيانات من جميع الصفحات
        try:
            result['grades_status'] = self.get_grades_status()
            result['current_semester_transcript'] = self.get_current_semester_transcript()
            result['all_semesters_transcript'] = self.get_all_semesters_transcript()
            result['remaining_courses'] = self.get_remaining_courses()
            result['success'] = True
        except Exception as e:
            result['error'] = f"خطأ في جمع البيانات: {str(e)}"
            logger.error(result['error'])
        
        return result
    
    def close(self):
        """إغلاق الجلسة."""
        self.session.close()
        self.logged_in = False
        self._login_retry_count = 0  # إعادة تعيين عداد المحاولات

