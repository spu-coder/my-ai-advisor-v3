"""
Configuration Manager Module
============================
This module handles loading and caching of configuration files.
Provides centralized configuration management for the application.

وحدة إدارة التكوين
===================
هذه الوحدة تتعامل مع تحميل وتخزين ملفات التكوين.
توفر إدارة مركزية للتكوين للتطبيق.
"""

import json
import os
import logging
from typing import Dict, Any

logger = logging.getLogger("CONFIG_MANAGER")
CONFIG_FILE_PATH = os.getenv("CONFIG_FILE_PATH", "/app/config/settings.json")
_CONFIG_CACHE: Dict[str, Any] = {}


def load_config() -> Dict[str, Any]:
    """
    Load configuration file (settings.json) into memory cache.
    / تحميل ملف التكوين (settings.json) إلى الذاكرة المؤقتة.
    
    Returns:
        Dictionary containing configuration data / قاموس يحتوي على بيانات التكوين
    """
    global _CONFIG_CACHE
    if _CONFIG_CACHE:
        return _CONFIG_CACHE
        
    try:
        with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
            _CONFIG_CACHE = json.load(f)
            logger.info(f"Configuration loaded successfully from {CONFIG_FILE_PATH}")
            return _CONFIG_CACHE
    except FileNotFoundError:
        logger.error(f"Configuration file not found at {CONFIG_FILE_PATH}. Using empty config.")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from configuration file: {e}")
        return {}
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading configuration: {e}")
        return {}

def get_config(key: str, default: Any = None) -> Any:
    """
    Get a value from configuration using a key.
    / الحصول على قيمة من التكوين باستخدام مفتاح.
    
    Args:
        key: Configuration key / مفتاح التكوين
        default: Default value if key not found / القيمة الافتراضية إذا لم يُعثر على المفتاح
        
    Returns:
        Configuration value or default / قيمة التكوين أو القيمة الافتراضية
    """
    config = load_config()
    return config.get(key, default)

# تحميل التكوين عند استيراد الملف لأول مرة
load_config()
