from datetime import datetime
from models import db, Account, JournalEntry, JournalDetail, SystemSettings
from flask_login import current_user


class AccountingSystem:

    @staticmethod
    def get_account_balance(account_number):
        account = Account.query.filter_by(account_number=account_number).first()
        return account.balance if account else 0.0

    @staticmethod
    def create_journal_entry(date, description, entries, reference_prefix="JE", notes=""):
        """إنشاء قيد يومي"""
        total_debit = sum(entry[1] for entry in entries)
        total_credit = sum(entry[2] for entry in entries)

        if abs(total_debit - total_credit) > 0.01:
            raise ValueError(f"القيد غير متوازن: مدين={total_debit}, دائن={total_credit}")

        ref_number = f"{reference_prefix}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        try:
            from flask_login import current_user
            created_by = current_user.username if current_user and current_user.is_authenticated else 'system'
        except:
            created_by = 'system'

        journal_entry = JournalEntry(
            date=date,
            description=description,
            reference_number=ref_number,
            created_by=created_by,
            notes=notes,
            is_posted=True
        )
        db.session.add(journal_entry)
        db.session.flush()

        for account_number, debit, credit, entry_notes in entries:
            account = Account.query.filter_by(account_number=account_number).first()
            if not account:
                raise ValueError(f"الحساب {account_number} غير موجود")

            detail = JournalDetail(
                entry_id=journal_entry.id,
                account_id=account.id,
                debit=debit,
                credit=credit,
                notes=entry_notes
            )
            db.session.add(detail)

            if account.account_type in ['asset', 'expense']:
                account.balance = account.balance + debit - credit
            else:
                account.balance = account.balance - debit + credit

        db.session.commit()
        return journal_entry

    @staticmethod
    def create_production_journal_entry(production):
        """
        إنشاء قيد يومي للإنتاج
        توزيع الأجر بين الخياطة الرئيسية والمساعدة (رسمية أو مؤقتة)
        """
        settings = SystemSettings.query.first()

        quantity = production.quantity
        price = production.bag_type.price_per_bag
        total_amount = quantity * price

        # العمولة: 0.2 ريال × عدد الأكياس
        contractor_commission = settings.contractor_amount * quantity if settings else 0.0

        insurance_amount = settings.insurance_amount if settings else 0.0
        tax_amount = settings.tax_amount if settings else 0.0

        insurance = total_amount * (
                    insurance_amount / 100) if settings and settings.insurance_type == 'percentage' else insurance_amount
        tax = total_amount * (tax_amount / 100) if settings and settings.tax_type == 'percentage' else tax_amount

        total_deductions = contractor_commission + insurance + tax
        net_payable = total_amount - total_deductions

        # توزيع 50% للخياطة و 50% للمساعدة
        operator_share = net_payable / 2
        assistant_share = net_payable / 2

        # تحديد اسم المساعدة
        if production.temporary_assistant:
            assistant_name = production.temporary_assistant
        else:
            assistant_name = production.machine.assistant_name

        operator_name = production.machine.operator_name

        # القيد المحاسبي الصحيح:
        # المدين: إجمالي اجر المكينة (13,000)
        # الدائن: مستحق الخياطة (6,240) + مستحق المساعدة (6,240) + عمولة (520) + تأمين (0) + ضريبة (0)
        # المجموع: 13,000 = 13,000 ✅

        entries = [
            # مدين: أجور الخياطات (إجمالي اجر المكينة)
            ('5000', total_amount, 0.0, f"إجمالي إنتاج مكينة {production.machine.name} - {quantity} كيس"),

            # دائن: مستحق الخياطة الرئيسية
            ('1200', 0.0, operator_share, f"مستحق للخياطة {operator_name} (50% من صافي المكينة)"),
        ]

        # إضافة مستحق المساعدة إذا وجدت
        if assistant_name:
            entries.append(('1200', 0.0, assistant_share, f"مستحق للمساعدة {assistant_name} (50% من صافي المكينة)"))

        # إضافة الخصومات
        entries.append(('2000', 0.0, contractor_commission, f"عمولة المتعهدة"))
        entries.append(('2100', 0.0, insurance, f"تأمينات"))
        entries.append(('2200', 0.0, tax, f"ضرائب"))

        # حساب المجاميع
        total_debit = total_amount
        total_credit = operator_share + (
            assistant_share if assistant_name else 0) + contractor_commission + insurance + tax

        print(f"\n{'=' * 60}")
        print(f"📝 قيد إنتاج - مكينة: {production.machine.name}")
        print(f"{'=' * 60}")
        print(f"📦 الكمية: {quantity} كيس")
        print(f"💰 سعر الكيس: {price} ريال")
        print(f"💵 إجمالي اجر المكينة: {total_amount} ريال")
        print(f"{'-' * 50}")
        print(f"📉 الخصومات:")
        print(f"   • عمولة المتعهدة: {contractor_commission} ريال")
        print(f"   • تأمينات: {insurance} ريال")
        print(f"   • ضريبة: {tax} ريال")
        print(f"   • إجمالي الخصومات: {total_deductions} ريال")
        print(f"{'-' * 50}")
        print(f"✅ صافي اجر المكينة: {net_payable} ريال")
        print(f"{'-' * 50}")
        print(f"👩‍🔧 توزيع صافي اجر المكينة:")
        print(f"   • الخياطة الرئيسية ({operator_name}): {operator_share} ريال (50%)")
        if assistant_name:
            print(f"   • المساعدة ({assistant_name}): {assistant_share} ريال (50%)")
        print(f"{'=' * 60}")
        print(f"🔢 ميزان القيد: مدين={total_debit} | دائن={total_credit}")

        if abs(total_debit - total_credit) > 0.01:
            raise ValueError(f"القيد غير متوازن: مدين={total_debit}, دائن={total_credit}")

        print(f"✅ القيد متوازن!\n")

        description = f"قيد إنتاج - {production.machine.name} - {quantity} كيس"
        journal_entry = AccountingSystem.create_journal_entry(
            production.date,
            description,
            entries,
            "PROD"
        )

        production.journal_entry_id = journal_entry.id
        db.session.commit()

        return journal_entry

    @staticmethod
    def create_advance_journal_entry(advance):
        entries = [
            ('1200', advance.amount, 0.0, f"سلفة للعاملة {advance.worker_name}"),
            ('1000', 0.0, advance.amount, f"صرف نقدي"),
        ]
        journal_entry = AccountingSystem.create_journal_entry(
            advance.date,
            f"سلفة للعاملة {advance.worker_name} - مبلغ {advance.amount} ريال",
            entries,
            "ADV"
        )
        advance.journal_entry_id = journal_entry.id
        db.session.commit()
        return journal_entry

    @staticmethod
    def create_payment_journal_entry(payment):
        """إنشاء قيد محاسبي للدفع"""
        from accounting import AccountingSystem

        entries = [
            ('2000', payment.amount, 0.0, f"تسوية حساب المتعهدة - مستخلص رقم {payment.settlement_id}"),
            ('1000', 0.0, payment.amount, f"صرف نقدي - طريقة الدفع {payment.payment_method}"),
        ]

        journal_entry = AccountingSystem.create_journal_entry(
            payment.payment_date,
            f"دفع مستخلص رقم {payment.settlement_id} للمتعهدة",
            entries,
            "PAY"
        )

        return journal_entry

    @staticmethod
    def create_settlement_journal_entry(settlement):
        """إنشاء قيد يومي لتسوية المستخلص"""
        entries = [
            ('2100', settlement.total_insurance, 0.0, "سداد التأمينات"),
            ('2200', settlement.total_tax, 0.0, "سداد الضرائب"),
            ('1000', 0.0, settlement.total_insurance + settlement.total_tax + settlement.advance_to_contractor,
             "صرف نقدي"),
        ]

        # إذا كان هناك سلفة للمتعهدة، أضفها كقيد منفصل
        if settlement.advance_to_contractor > 0:
            entries.insert(0, ('1300', settlement.advance_to_contractor, 0.0, "تسوية سلفة المتعهدة"))

        journal_entry = AccountingSystem.create_journal_entry(
            datetime.now(),
            f"تسوية مستخلص {settlement.settlement_type} - فترة {settlement.period_text}",
            entries,
            "SETT"
        )
        settlement.journal_entry_id = journal_entry.id
        db.session.commit()
        return journal_entry

    @staticmethod
    def get_trial_balance(up_to_date=None):
        accounts = Account.query.filter_by(is_active=True).all()
        trial_balance = []
        total_debit = 0
        total_credit = 0

        for account in accounts:
            if account.account_type in ['asset', 'expense']:
                if account.balance > 0:
                    debit = account.balance
                    credit = 0
                else:
                    debit = 0
                    credit = abs(account.balance)
            else:
                if account.balance > 0:
                    debit = 0
                    credit = account.balance
                else:
                    debit = abs(account.balance)
                    credit = 0

            total_debit += debit
            total_credit += credit

            trial_balance.append({
                'account_number': account.account_number,
                'account_name': account.account_name,
                'account_type': account.account_type_ar,
                'debit': debit,
                'credit': credit,
                'balance': abs(account.balance)
            })

        return {
            'accounts': trial_balance,
            'total_debit': total_debit,
            'total_credit': total_credit,
            'is_balanced': abs(total_debit - total_credit) < 0.01
        }

    @staticmethod
    def get_income_statement(start_date, end_date):
        from sqlalchemy import func

        revenue_account = Account.query.filter_by(account_number='4000').first()
        total_revenue = 0
        if revenue_account:
            result = db.session.query(func.sum(JournalDetail.debit)).filter(
                JournalDetail.account_id == revenue_account.id,
                JournalEntry.date.between(start_date, end_date),
                JournalEntry.id == JournalDetail.entry_id
            ).scalar()
            total_revenue = result or 0

        expense_accounts = ['5000', '5100', '5200', '5300']
        total_expenses = 0
        wages = 0
        commission = 0
        insurance = 0
        tax = 0

        for acc_num in expense_accounts:
            account = Account.query.filter_by(account_number=acc_num).first()
            if account:
                result = db.session.query(func.sum(JournalDetail.credit)).filter(
                    JournalDetail.account_id == account.id,
                    JournalEntry.date.between(start_date, end_date),
                    JournalEntry.id == JournalDetail.entry_id
                ).scalar()
                amount = result or 0
                total_expenses += amount

                if acc_num == '5000':
                    wages = amount
                elif acc_num == '5100':
                    commission = amount
                elif acc_num == '5200':
                    insurance = amount
                elif acc_num == '5300':
                    tax = amount

        net_income = total_revenue - total_expenses

        return {
            'total_revenue': total_revenue,
            'total_expenses': total_expenses,
            'net_income': net_income,
            'start_date': start_date,
            'end_date': end_date,
            'wages': wages,
            'commission': commission,
            'insurance': insurance,
            'tax': tax
        }