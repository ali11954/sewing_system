from app import app
import os

if __name__ == '__main__':
    # تعطيل PostgreSQL مؤقتاً للتشغيل المحلي
    # (سيتم استخدام SQLite محلياً)
    os.environ['DATABASE_URL'] = ''

    print("\n" + "=" * 50)
    print("🚀 تشغيل نظام معمل الخياطات (محلي)")
    print("=" * 50)
    print("📍 http://127.0.0.1:5000")
    print("🔑 الدخول: admin / admin123")
    print("📊 قاعدة البيانات: SQLite (محلي)")
    print("=" * 50 + "\n")

    app.run(debug=True, host='127.0.0.1', port=5000, use_reloader=True)