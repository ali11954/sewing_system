from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


# ==================== المستخدمين والصلاحيات ====================

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(100))
    role = db.Column(db.String(20), default='viewer')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return f'<User {self.username}>'


# ==================== المكائن ====================

class Machine(db.Model):
    __tablename__ = 'machines'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True)
    name = db.Column(db.String(50))
    operator_name = db.Column(db.String(100))
    operator_phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    productions = db.relationship('Production', backref='machine', lazy=True)

    def __repr__(self):
        return f'<Machine {self.name}>'


# ==================== أنواع الأكياس ====================

class BagType(db.Model):
    __tablename__ = 'bag_types'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    size = db.Column(db.String(20))
    price_per_bag = db.Column(db.Float)
    is_active = db.Column(db.Boolean, default=True)

    productions = db.relationship('Production', backref='bag_type', lazy=True)

    @property
    def full_name(self):
        return f"{self.name} - {self.size}"

    def __repr__(self):
        return f'<BagType {self.full_name}>'


# ==================== الإنتاج ====================

class Production(db.Model):
    __tablename__ = 'productions'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=datetime.now)
    machine_id = db.Column(db.Integer, db.ForeignKey('machines.id'))
    bag_type_id = db.Column(db.Integer, db.ForeignKey('bag_types.id'))
    quantity = db.Column(db.Integer, nullable=False)
    worker_name = db.Column(db.String(100))
    is_temporary = db.Column(db.Boolean, default=False)
    notes = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.now)
    created_by = db.Column(db.String(50))
    journal_entry_id = db.Column(db.Integer, db.ForeignKey('journal_entries.id'))

    @property
    def total_amount(self):
        return self.quantity * self.bag_type.price_per_bag if self.bag_type else 0

    def __repr__(self):
        return f'<Production {self.date} - Qty:{self.quantity}>'


# ==================== السلف ====================

class Advance(db.Model):
    __tablename__ = 'advances'

    id = db.Column(db.Integer, primary_key=True)
    worker_name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)  # يجب أن تكون موجبة فقط
    date = db.Column(db.Date, default=datetime.now)
    is_temporary = db.Column(db.Boolean, default=False)
    notes = db.Column(db.String(200))
    created_by = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.now)
    journal_entry_id = db.Column(db.Integer, db.ForeignKey('journal_entries.id'))

    @property
    def is_advance(self):
        """تأكيد أن المبلغ موجب (سلفة)"""
        return self.amount > 0

    def __repr__(self):
        return f'<Advance {self.worker_name}: {self.amount}>'


class SalaryPayment(db.Model):
    """جدول منفصل لدفع الأجور"""
    __tablename__ = 'salary_payments'

    id = db.Column(db.Integer, primary_key=True)
    worker_name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)  # المبلغ المدفوع
    payment_date = db.Column(db.Date, default=datetime.now)
    payment_method = db.Column(db.String(20))  # cash, bank, check
    settlement_id = db.Column(db.Integer, db.ForeignKey('settlements.id'))
    notes = db.Column(db.String(200))
    created_by = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.now)

    settlement = db.relationship('Settlement', backref='salary_payments', lazy=True)

# ==================== الحسابات المحاسبية ====================

class Account(db.Model):
    __tablename__ = 'accounts'

    id = db.Column(db.Integer, primary_key=True)
    account_number = db.Column(db.String(20), unique=True, nullable=False)
    account_name = db.Column(db.String(100), nullable=False)
    account_type = db.Column(db.String(50))
    parent_account = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    balance = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    description = db.Column(db.String(200))

    children = db.relationship('Account', backref=db.backref('parent', remote_side=[id]))
    journal_details = db.relationship('JournalDetail', backref='account', lazy=True)

    @property
    def account_type_ar(self):
        types = {
            'asset': 'أصل',
            'liability': 'خصم',
            'equity': 'حقوق ملكية',
            'revenue': 'إيراد',
            'expense': 'مصروف'
        }
        return types.get(self.account_type, self.account_type)

    def __repr__(self):
        return f'<Account {self.account_number} - {self.account_name}>'


# ==================== القيود اليومية ====================

class JournalEntry(db.Model):
    __tablename__ = 'journal_entries'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=datetime.now)
    description = db.Column(db.String(200), nullable=False)
    reference_number = db.Column(db.String(50), unique=True)
    is_posted = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.now)
    notes = db.Column(db.String(200))

    details = db.relationship('JournalDetail', backref='entry', lazy=True, cascade='all, delete-orphan')
    productions = db.relationship('Production', backref='journal_entry', lazy=True)
    advances = db.relationship('Advance', backref='journal_entry', lazy=True)
    settlements = db.relationship('Settlement', backref='journal_entry', lazy=True)

    @property
    def total_debit(self):
        return sum(d.debit for d in self.details)

    @property
    def total_credit(self):
        return sum(d.credit for d in self.details)

    def is_balanced(self):
        return abs(self.total_debit - self.total_credit) < 0.01

    def __repr__(self):
        return f'<JournalEntry {self.reference_number}>'


class JournalDetail(db.Model):
    __tablename__ = 'journal_details'

    id = db.Column(db.Integer, primary_key=True)
    entry_id = db.Column(db.Integer, db.ForeignKey('journal_entries.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    debit = db.Column(db.Float, default=0.0)
    credit = db.Column(db.Float, default=0.0)
    notes = db.Column(db.String(200))

    def __repr__(self):
        return f'<JournalDetail Entry:{self.entry_id}>'


# ==================== المستخلصات ====================

class Settlement(db.Model):
    __tablename__ = 'settlements'

    id = db.Column(db.Integer, primary_key=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    settlement_type = db.Column(db.String(20))
    total_production_amount = db.Column(db.Float, default=0.0)
    contractor_commission = db.Column(db.Float, default=0.0)
    total_insurance = db.Column(db.Float, default=0.0)
    total_tax = db.Column(db.Float, default=0.0)
    total_advances = db.Column(db.Float, default=0.0)
    net_amount = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='draft')  # draft, posted, paid_to_contractor, distributed
    created_date = db.Column(db.Date, default=datetime.now)
    created_by = db.Column(db.String(50))
    journal_entry_id = db.Column(db.Integer, db.ForeignKey('journal_entries.id'))

    @property
    def period_text(self):
        return f"{self.start_date.strftime('%Y-%m-%d')} إلى {self.end_date.strftime('%Y-%m-%d')}"

    def __repr__(self):
        return f'<Settlement {self.period_text}>'


# ==================== إعدادات النظام ====================

class SystemSettings(db.Model):
    __tablename__ = 'system_settings'

    id = db.Column(db.Integer, primary_key=True)
    contractor_percentage = db.Column(db.Float, default=0.0)
    insurance_amount = db.Column(db.Float, default=0.0)
    insurance_type = db.Column(db.String(10), default='percentage')
    tax_amount = db.Column(db.Float, default=0.0)
    tax_type = db.Column(db.String(10), default='percentage')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    updated_by = db.Column(db.String(50))

    def __repr__(self):
        return f'<SystemSettings {self.id}>'


# ==================== المدفوعات ====================

class PaymentStatus:
    PENDING = 'pending'
    PAID_TO_CONTRACTOR = 'paid_to_contractor'
    DISTRIBUTED = 'distributed'
    COMPLETED = 'completed'


class Payment(db.Model):
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    settlement_id = db.Column(db.Integer, db.ForeignKey('settlements.id'))
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.Date, default=datetime.now)
    payment_method = db.Column(db.String(20))
    reference_number = db.Column(db.String(50))
    status = db.Column(db.String(20), default=PaymentStatus.PENDING)
    notes = db.Column(db.String(200))
    created_by = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.now)

    settlement = db.relationship('Settlement', backref='payments', lazy=True)
    worker_payments = db.relationship('WorkerPayment', backref='payment', lazy=True)


class WorkerPayment(db.Model):
    __tablename__ = 'worker_payments'

    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'))
    worker_name = db.Column(db.String(100), nullable=False)
    worker_type = db.Column(db.String(20))
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.Date, default=datetime.now)
    payment_method = db.Column(db.String(20))
    receipt_number = db.Column(db.String(50))
    is_signed = db.Column(db.Boolean, default=False)
    signature_date = db.Column(db.Date)
    notes = db.Column(db.String(200))
    created_by = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return f'<WorkerPayment {self.worker_name}: {self.amount}>'


# ==================== دوال إنشاء الجداول الافتراضية ====================

def init_default_accounts():
    """إنشاء الحسابات المحاسبية الافتراضية"""
    default_accounts = [
        ('1000', 'النقدية', 'asset', None),
        ('1100', 'البنك', 'asset', None),
        ('1200', 'السلف للعاملات', 'asset', None),
        ('1300', 'مدينون - متعهدة الخياطة', 'asset', None),
        ('2000', 'دائنون - متعهدة الخياطة', 'liability', None),
        ('2100', 'ضرائب مستحقة', 'liability', None),
        ('2200', 'تأمينات مستحقة', 'liability', None),
        ('3000', 'رأس المال', 'equity', None),
        ('3100', 'الأرباح المحتجزة', 'equity', None),
        ('4000', 'إيراد الخياطة', 'revenue', None),
        ('5000', 'أجور الخياطات', 'expense', None),
        ('5100', 'عمولة المتعهدة', 'expense', None),
        ('5200', 'مصروف التأمينات', 'expense', None),
        ('5300', 'مصروف الضرائب', 'expense', None),
    ]

    for acc_num, acc_name, acc_type, parent in default_accounts:
        if not Account.query.filter_by(account_number=acc_num).first():
            account = Account(
                account_number=acc_num,
                account_name=acc_name,
                account_type=acc_type,
                parent_account=parent,
                balance=0.0
            )
            db.session.add(account)

    db.session.commit()


def init_default_settings():
    """إنشاء الإعدادات الافتراضية"""
    if not SystemSettings.query.first():
        settings = SystemSettings(
            contractor_percentage=10.0,
            insurance_amount=5.0,
            insurance_type='percentage',
            tax_amount=5.0,
            tax_type='percentage'
        )
        db.session.add(settings)
        db.session.commit()


def init_default_user():
    """إنشاء مستخدم افتراضي (admin/admin123)"""
    from werkzeug.security import generate_password_hash

    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            password=generate_password_hash('admin123'),
            full_name='مدير النظام',
            role='admin',
            is_active=True
        )
        db.session.add(admin)
        db.session.commit()