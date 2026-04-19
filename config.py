import os


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-change-this-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///sewing.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # إعدادات التطبيق
    APP_NAME = 'نظام معمل الخياطات'
    APP_VERSION = '1.0.0'

    # الإعدادات الافتراضية للنسب
    DEFAULT_CONTRACTOR_PERCENTAGE = 0.0
    DEFAULT_INSURANCE_AMOUNT = 0.0
    DEFAULT_TAX_AMOUNT = 0.0

    # إعدادات الجلسة
    PERMANENT_SESSION_LIFETIME = 86400  # 24 ساعة