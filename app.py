from flask import Flask
from flask_login import LoginManager
from models import db, init_default_accounts, init_default_settings, init_default_user
from routes import register_routes
from config import Config
import logging

# تعطيل سجلات التحذير غير الضرورية
logging.getLogger('watchdog').setLevel(logging.ERROR)
logging.getLogger('werkzeug').setLevel(logging.WARNING)

# إنشاء التطبيق
app = Flask(__name__)
app.config.from_object(Config)

app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['TEMPLATES_AUTO_RELOAD'] = False

# تهيئة قاعدة البيانات
db.init_app(app)

# تهيئة Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    from models import User
    # استخدام get بدلاً من query.get لتجنب التحذير
    return db.session.get(User, int(user_id))


# تسجيل المسارات
register_routes(app)


# إنشاء الجداول والبيانات الأساسية فقط (بدون بيانات افتراضية)
with app.app_context():
    db.create_all()
    init_default_accounts()      # إنشاء الحسابات المحاسبية فقط
    init_default_settings()      # إنشاء الإعدادات الافتراضية
    init_default_user()          # إنشاء المستخدم admin فقط
    print("\n✅ تم إنشاء الجداول والحسابات الأساسية بنجاح")
    print("📌 النظام جاهز للاستخدام - يمكنك إضافة البيانات يدوياً")

if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("🚀 تشغيل نظام معمل الخياطات")
    print("=" * 50)
    print("📍 http://127.0.0.1:5000")
    print("🔑 الدخول: admin / admin123")
    print("=" * 50 + "\n")

    app.run(debug=False, host='0.0.0.0', port=5000, use_reloader=False)