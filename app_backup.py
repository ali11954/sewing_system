from flask import Flask
from flask_login import LoginManager
from models import db, init_default_accounts, init_default_settings, init_default_user
from routes import register_routes
from config import Config
import logging
import sys
from datetime import datetime, timedelta

# تعطيل سجلات التحذير غير الضرورية
logging.getLogger('watchdog').setLevel(logging.ERROR)
logging.getLogger('werkzeug').setLevel(logging.WARNING)

# إنشاء التطبيق
app = Flask(__name__)
app.config.from_object(Config)

# إضافة إعدادات إضافية لمنع إعادة التحميل المفرطة
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
    return User.query.get(int(user_id))


# تسجيل المسارات
register_routes(app)


# دالة لإضافة البيانات الافتراضية
def init_demo_data():
    from models import BagType, Machine, Production, Advance, SystemSettings

    # التحقق إذا كانت البيانات موجودة مسبقاً
    if BagType.query.count() > 0:
        print("✅ البيانات الافتراضية موجودة مسبقاً")
        return

    print("📦 جاري إضافة البيانات الافتراضية...")

    # 1. إضافة أنواع الأكياس
    bag_types = [
        BagType(name='سكر', size='1كجم', price_per_bag=0.50, is_active=True),
        BagType(name='سكر', size='5كجم', price_per_bag=2.00, is_active=True),
        BagType(name='سكر', size='10كجم', price_per_bag=3.50, is_active=True),
        BagType(name='رز', size='1كجم', price_per_bag=0.75, is_active=True),
        BagType(name='رز', size='5كجم', price_per_bag=3.00, is_active=True),
        BagType(name='رز', size='10كجم', price_per_bag=5.00, is_active=True),
        BagType(name='دقيق', size='1كجم', price_per_bag=0.40, is_active=True),
        BagType(name='دقيق', size='5كجم', price_per_bag=1.50, is_active=True),
        BagType(name='دقيق', size='10كجم', price_per_bag=2.50, is_active=True),
        BagType(name='شعير', size='20كجم', price_per_bag=4.00, is_active=True),
        BagType(name='ذرة', size='25كجم', price_per_bag=5.00, is_active=True),
    ]

    for bt in bag_types:
        db.session.add(bt)
    db.session.commit()
    print(f"✅ تم إضافة {len(bag_types)} نوع من الأكياس")

    # 2. إضافة المكائن والخياطات
    machines = [
        Machine(code='M001', name='مكينة خياطة 1', operator_name='سارة محمد', operator_phone='0501111111',
                is_active=True),
        Machine(code='M002', name='مكينة خياطة 2', operator_name='نورة علي', operator_phone='0502222222',
                is_active=True),
        Machine(code='M003', name='مكينة خياطة 3', operator_name='فاطمة حسن', operator_phone='0503333333',
                is_active=True),
        Machine(code='M004', name='مكينة خياطة 4', operator_name='خديجة أحمد', operator_phone='0504444444',
                is_active=True),
        Machine(code='M005', name='مكينة خياطة 5', operator_name='عائشة عمر', operator_phone='0505555555',
                is_active=True),
    ]

    for m in machines:
        db.session.add(m)
    db.session.commit()
    print(f"✅ تم إضافة {len(machines)} مكينة وخياطة")

    # 3. إضافة إنتاج للأيام السابقة
    today = datetime.now().date()

    productions_data = [
        # اليوم
        (today, 1, 1, 150, None, False),  # مكينة 1 - سكر 1كجم - 150 كيس
        (today, 2, 4, 100, None, False),  # مكينة 2 - رز 1كجم - 100 كيس
        (today, 3, 7, 200, None, False),  # مكينة 3 - دقيق 1كجم - 200 كيس
        (today, 1, 2, 80, None, False),  # مكينة 1 - سكر 5كجم - 80 كيس
        (today, 4, 5, 60, 'منى خالد', True),  # عاملة مؤقتة - رز 5كجم - 60 كيس

        # أمس
        (today - timedelta(days=1), 1, 1, 120, None, False),
        (today - timedelta(days=1), 2, 4, 90, None, False),
        (today - timedelta(days=1), 3, 7, 180, None, False),
        (today - timedelta(days=1), 5, 10, 50, None, False),  # مكينة 5 - شعير 20كجم

        # قبل يومين
        (today - timedelta(days=2), 1, 2, 70, None, False),
        (today - timedelta(days=2), 2, 5, 85, None, False),
        (today - timedelta(days=2), 4, 8, 110, 'ليلى سمير', True),  # عاملة مؤقتة

        # قبل 3 أيام
        (today - timedelta(days=3), 3, 3, 95, None, False),
        (today - timedelta(days=3), 1, 1, 130, None, False),
        (today - timedelta(days=3), 5, 11, 45, None, False),

        # قبل 4 أيام
        (today - timedelta(days=4), 2, 4, 110, None, False),
        (today - timedelta(days=4), 3, 7, 160, None, False),
        (today - timedelta(days=4), 1, 3, 55, None, False),
    ]

    for date, machine_id, bag_type_id, qty, worker, is_temp in productions_data:
        production = Production(
            date=date,
            machine_id=machine_id,
            bag_type_id=bag_type_id,
            quantity=qty,
            worker_name=worker,
            is_temporary=is_temp,
            notes='بيانات تجريبية',
            created_by='admin'
        )
        db.session.add(production)

    db.session.commit()
    print(f"✅ تم إضافة {len(productions_data)} عملية إنتاج")

    # 4. إضافة سلف للخياطات
    advances_data = [
        (today - timedelta(days=5), 'سارة محمد', 500.00, False, 'سلفة شهرية'),
        (today - timedelta(days=3), 'نورة علي', 300.00, False, 'سلفة عاجلة'),
        (today - timedelta(days=2), 'فاطمة حسن', 450.00, False, 'سلفة'),
        (today - timedelta(days=1), 'منى خالد', 200.00, True, 'سلفة عاملة مؤقتة'),
        (today, 'خديجة أحمد', 350.00, False, 'سلفة'),
        (today - timedelta(days=4), 'ليلى سمير', 150.00, True, 'سلفة'),
    ]

    for date, worker, amount, is_temp, notes in advances_data:
        advance = Advance(
            date=date,
            worker_name=worker,
            amount=amount,
            is_temporary=is_temp,
            notes=notes,
            created_by='admin'
        )
        db.session.add(advance)

    db.session.commit()
    print(f"✅ تم إضافة {len(advances_data)} سلفة")

    # 5. تحديث إعدادات النظام
    settings = SystemSettings.query.first()
    if settings:
        settings.contractor_percentage = 10.0  # 10% عمولة المتعهدة
        settings.insurance_amount = 2.0  # 2% تأمينات
        settings.insurance_type = 'percentage'
        settings.tax_amount = 1.0  # 1% ضريبة
        settings.tax_type = 'percentage'
        settings.updated_by = 'admin'
        db.session.commit()
        print("✅ تم تحديث إعدادات النظام (عمولة 10%، تأمين 2%، ضريبة 1%)")

    print("\n🎉 تم إضافة جميع البيانات الافتراضية بنجاح!")
    print("=" * 50)
    print("📊 ملخص البيانات:")
    print(f"   - أنواع الأكياس: {BagType.query.count()}")
    print(f"   - المكائن والخياطات: {Machine.query.count()}")
    print(f"   - عمليات الإنتاج: {Production.query.count()}")
    print(f"   - السلف: {Advance.query.count()}")
    print("=" * 50)


# إنشاء الجداول والبيانات الافتراضية
with app.app_context():
    db.create_all()
    init_default_accounts()
    init_default_settings()
    init_default_user()
    init_demo_data()  # إضافة البيانات الافتراضية

if __name__ == '__main__':
    # تشغيل التطبيق
    print("\n" + "=" * 50)
    print("🚀 تشغيل نظام معمل الخياطات")
    print("=" * 50)
    print("📍 العنوان المحلي: http://127.0.0.1:5000")
    print("📍 عنوان الشبكة: http://192.168.16.41:5000")
    print("🔑 الدخول: admin / admin123")
    print("=" * 50 + "\n")

    app.run(debug=False, host='0.0.0.0', port=5000, use_reloader=False)