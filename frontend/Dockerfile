# استخدم صورة بايثون أساسية
FROM python:3.11-slim

# تعيين متغيرات البيئة
ENV PYTHONUNBUFFERED 1
ENV APP_HOME /app
WORKDIR $APP_HOME

# نسخ ملف المتطلبات أولاً للاستفادة من الكاش
COPY requirements.txt .

# تثبيت التبعيات
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي كود التطبيق
COPY . $APP_HOME

EXPOSE 8501

# تشغيل تطبيق Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
