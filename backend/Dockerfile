# استخدم صورة بايثون أساسية
FROM python:3.11-slim

# تعيين متغيرات البيئة
ENV PYTHONUNBUFFERED 1
ENV APP_HOME /app
WORKDIR $APP_HOME

# تثبيت التبعيات اللازمة لـ PDF processing, OCR, و image processing
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt-dev \
    libmagic1 \
    tesseract-ocr \
    tesseract-ocr-ara \
    tesseract-ocr-eng \
    libtesseract-dev \
    poppler-utils \
    libpoppler-cpp-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# نسخ ملف requirements.txt وتثبيت التبعيات
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات التطبيق
COPY . $APP_HOME

EXPOSE 8000

# تشغيل التطبيق باستخدام Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
