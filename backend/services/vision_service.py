"""
Vision Service - Gemini Vision API
==================================
Comprehensive OCR for all document types

OCR شامل لجميع أنواع المستندات
"""

import os
import logging
import io
from typing import Dict, Any, List, Optional
from PIL import Image

logger = logging.getLogger("VISION_SERVICE")

# Try to import Gemini
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("Google Generative AI not available. Install with: pip install google-generativeai")

# Configuration
GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_VISION_MODEL", "gemini-1.5-pro-vision")
USE_GEMINI = os.getenv("USE_GEMINI_OCR", "true").lower() == "true"

# Initialize Gemini if available
if GEMINI_AVAILABLE and GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        logger.info("Google Gemini API configured successfully")
    except Exception as e:
        logger.warning(f"Failed to configure Gemini API: {e}")
        GEMINI_AVAILABLE = False


class VisionService:
    """
    Vision service for OCR and image analysis
    خدمة الرؤية لـ OCR وتحليل الصور
    
    Uses Gemini Vision API for high-accuracy OCR
    يستخدم Gemini Vision API لـ OCR عالي الدقة
    """
    
    def __init__(self):
        """
        Initialize Vision Service
        
        تهيئة خدمة الرؤية
        
        Raises:
            RuntimeError: If Gemini API key is not configured
        """
        if not GEMINI_AVAILABLE:
            logger.warning("Gemini Vision API not available. OCR will use fallback methods.")
            self.model = None
        else:
            try:
                self.model = genai.GenerativeModel(GEMINI_MODEL)
                logger.info(f"Vision Service initialized with model: {GEMINI_MODEL}")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini model: {e}")
                self.model = None
    
    async def extract_text_from_image(
        self,
        image_bytes: bytes,
        language: str = "ar+en",
        extract_tables: bool = True
    ) -> Dict[str, Any]:
        """
        Extract text from image using Gemini Vision
        
        استخراج النص من الصورة باستخدام Gemini Vision
        
        Args:
            image_bytes: Image bytes / بايتات الصورة
            language: Language (ar, en, ar+en) / اللغة
            extract_tables: Whether to extract tables / ما إذا كان سيتم استخراج الجداول
        
        Returns:
            Dictionary with extracted text, tables, confidence, and language
            / قاموس يحتوي على النص المستخرج، الجداول، الثقة، واللغة
        """
        if not self.model:
            return {
                "text": "",
                "tables": [],
                "confidence": 0.0,
                "language_detected": "unknown",
                "error": "Gemini Vision API not available"
            }
        
        try:
            # Load image
            image = Image.open(io.BytesIO(image_bytes))
            
            # Build prompt
            prompt = f"""
Extract ALL text from this image with highest accuracy.

Requirements:
1. Extract text in both Arabic and English
2. Preserve formatting and structure
3. If tables exist, extract them in structured format
4. Maintain line breaks and paragraphs

Output format (JSON):
{{
    "text": "extracted full text",
    "tables": [
        {{
            "headers": ["header1", "header2", ...],
            "rows": [
                ["cell1", "cell2", ...],
                ...
            ]
        }}
    ],
    "language": "ar" or "en" or "mixed"
}}
"""
            
            # Call Gemini
            response = self.model.generate_content([prompt, image])
            
            # Parse response
            result = self._parse_vision_response(response.text)
            
            return {
                "text": result.get("text", ""),
                "tables": result.get("tables", []),
                "confidence": 0.95,  # Gemini is highly accurate
                "language_detected": result.get("language", "unknown")
            }
            
        except Exception as e:
            logger.error(f"Error extracting text with Gemini Vision: {e}", exc_info=True)
            return {
                "text": "",
                "tables": [],
                "confidence": 0.0,
                "language_detected": "unknown",
                "error": str(e)
            }
    
    def _parse_vision_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse Gemini Vision API response
        
        تحليل استجابة Gemini Vision API
        
        Args:
            response_text: Raw response text / نص الاستجابة الخام
        
        Returns:
            Parsed result dictionary / قاموس النتيجة المحللة
        """
        import json
        import re
        
        try:
            # Try to extract JSON from response
            # Gemini might wrap JSON in markdown code blocks
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            
            # Try to find JSON object directly
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            
            # If no JSON found, treat entire response as text
            return {
                "text": response_text,
                "tables": [],
                "language": "mixed"
            }
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON from Gemini response: {e}")
            # Return raw text
            return {
                "text": response_text,
                "tables": [],
                "language": "unknown"
            }
    
    async def extract_tables_from_pdf_scan(
        self,
        pdf_bytes: bytes,
        page_number: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Extract tables from scanned PDF page
        
        استخراج الجداول من صفحة PDF ممسوحة ضوئياً
        
        Args:
            pdf_bytes: PDF file bytes / بايتات ملف PDF
            page_number: Page number to extract from / رقم الصفحة للاستخراج منها
        
        Returns:
            List of table dictionaries / قائمة قواميس الجداول
        """
        if not self.model:
            return []
        
        try:
            # Convert PDF page to image
            from pdf2image import convert_from_bytes
            
            images = convert_from_bytes(pdf_bytes, first_page=page_number, last_page=page_number)
            
            if not images:
                return []
            
            image = images[0]
            
            # Convert PIL Image to bytes
            img_bytes = io.BytesIO()
            image.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            
            # Extract tables using Gemini Vision
            result = await self.extract_text_from_image(
                image_bytes=img_bytes.read(),
                extract_tables=True
            )
            
            return result.get("tables", [])
            
        except Exception as e:
            logger.error(f"Error extracting tables from PDF scan: {e}", exc_info=True)
            return []
