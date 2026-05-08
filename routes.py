from flask import render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from sqlalchemy import func, and_
import json

from models import *
from accounting import AccountingSystem


def register_routes(app):
    # ==================== مصادقة المستخدم ====================

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')

            user = User.query.filter_by(username=username).first()

            if user and check_password_hash(user.password, password):
                login_user(user)
                session['role'] = user.role
                flash('تم تسجيل الدخول بنجاح', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'danger')

        return render_template('login.html')

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        session.clear()
        flash('تم تسجيل الخروج بنجاح', 'success')
        return redirect(url_for('login'))

    # ==================== لوحة التحكم ====================

    @app.route('/')
    @login_required
    def dashboard():
        # إحصائيات اليوم
        today = datetime.now().date()
        today_production = Production.query.filter_by(date=today).all()
        today_total = sum(p.total_amount for p in today_production)

        # إحصائيات الشهر
        first_day_of_month = today.replace(day=1)
        monthly_production = Production.query.filter(
            Production.date >= first_day_of_month
        ).all()
        monthly_total = sum(p.total_amount for p in monthly_production)

        # عدد المكائن النشطة
        active_machines = Machine.query.filter_by(is_active=True).count()

        # السلف غير المسددة
        recent_advances = Advance.query.order_by(Advance.date.desc()).limit(5).all()

        # آخر الإنتاج
        recent_production = Production.query.order_by(Production.date.desc()).limit(10).all()

        # إحصائيات سريعة
        stats = {
            'today_total': today_total,
            'today_count': len(today_production),
            'monthly_total': monthly_total,
            'monthly_count': len(monthly_production),
            'active_machines': active_machines,
            'total_bag_types': BagType.query.count()
        }

        return render_template('dashboard.html',
                               stats=stats,
                               recent_advances=recent_advances,
                               recent_production=recent_production)

    # ==================== إدارة الإنتاج ====================

    @app.route('/production')
    @login_required
    def production_list():
        productions = Production.query.order_by(Production.date.desc()).all()
        return render_template('production.html', productions=productions)

    @app.route('/production/add', methods=['GET', 'POST'])
    @login_required
    def add_production():
        if request.method == 'POST':
            date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
            machine_id = request.form.get('machine_id')
            bag_type_id = request.form.get('bag_type_id')
            quantity = int(request.form.get('quantity'))
            temporary_assistant = request.form.get('temporary_assistant')  # المساعدة المؤقتة
            notes = request.form.get('notes')

            # التحقق من عدم وجود إنتاج مكرر
            existing = Production.query.filter(
                Production.date == date,
                Production.machine_id == machine_id,
                Production.bag_type_id == bag_type_id
            ).first()

            if existing:
                flash(f'⚠️ لا يمكن إضافة إنتاج مكرر! يوجد إنتاج سابق لنفس المكينة ونفس نوع الكيس في هذا اليوم',
                      'danger')
                return redirect(url_for('add_production'))

            production = Production(
                date=date,
                machine_id=machine_id,
                bag_type_id=bag_type_id,
                quantity=quantity,
                temporary_assistant=temporary_assistant,  # المساعدة المؤقتة
                notes=notes,
                created_by=current_user.username
            )
            db.session.add(production)
            db.session.flush()

            AccountingSystem.create_production_journal_entry(production)

            flash('تم إضافة الإنتاج بنجاح', 'success')
            return redirect(url_for('production_list'))

        machines = Machine.query.filter_by(is_active=True).all()
        bag_types = BagType.query.filter_by(is_active=True).all()
        return render_template('production_form.html', machines=machines, bag_types=bag_types)

    @app.route('/production/edit/<int:id>', methods=['GET', 'POST'])
    @login_required
    def edit_production(id):
        production = Production.query.get_or_404(id)

        if request.method == 'POST':
            production.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
            production.machine_id = request.form.get('machine_id')
            production.bag_type_id = request.form.get('bag_type_id')
            production.quantity = int(request.form.get('quantity'))
            production.temporary_assistant = request.form.get('temporary_assistant')  # المساعدة المؤقتة
            production.notes = request.form.get('notes')

            db.session.commit()
            flash('تم تحديث الإنتاج بنجاح', 'success')
            return redirect(url_for('production_list'))

        machines = Machine.query.filter_by(is_active=True).all()
        bag_types = BagType.query.filter_by(is_active=True).all()
        return render_template('production_form.html', production=production, machines=machines, bag_types=bag_types)

    @app.route('/production/delete/<int:id>')
    @login_required
    def delete_production(id):
        production = Production.query.get_or_404(id)
        db.session.delete(production)
        db.session.commit()
        flash('تم حذف الإنتاج بنجاح', 'success')
        return redirect(url_for('production_list'))

    # ==================== إدارة المكائن ====================

    @app.route('/machines')
    @login_required
    def machines_list():
        machines = Machine.query.all()
        return render_template('machines.html', machines=machines)

    @app.route('/machines/add', methods=['POST'])
    @login_required
    def add_machine():
        machine = Machine(
            code=request.form.get('code'),
            name=request.form.get('name'),
            operator_name=request.form.get('operator_name'),
            operator_phone=request.form.get('operator_phone'),
            assistant_name=request.form.get('assistant_name'),
            assistant_phone=request.form.get('assistant_phone'),
            is_active=request.form.get('is_active') == 'on'
        )
        db.session.add(machine)
        db.session.commit()
        flash('تم إضافة المكينة بنجاح', 'success')
        return redirect(url_for('machines_list'))

    @app.route('/machines/edit/<int:id>', methods=['POST'])
    @login_required
    def edit_machine(id):
        machine = Machine.query.get_or_404(id)
        machine.code = request.form.get('code')
        machine.name = request.form.get('name')
        machine.operator_name = request.form.get('operator_name')
        machine.operator_phone = request.form.get('operator_phone')
        machine.assistant_name = request.form.get('assistant_name')
        machine.assistant_phone = request.form.get('assistant_phone')
        machine.is_active = request.form.get('is_active') == 'on'
        db.session.commit()
        flash('تم تحديث المكينة بنجاح', 'success')
        return redirect(url_for('machines_list'))

    # ==================== API للمكائن ====================
    @app.route('/api/machine/<int:id>')
    @login_required
    def api_machine(id):
        """API لجلب بيانات مكينة للتعديل"""
        machine = Machine.query.get_or_404(id)
        return jsonify({
            'success': True,
            'id': machine.id,
            'code': machine.code,
            'name': machine.name,
            'operator_name': machine.operator_name,
            'operator_phone': machine.operator_phone,
            'assistant_name': machine.assistant_name,
            'assistant_phone': machine.assistant_phone,
            'is_active': machine.is_active
        })

    @app.route('/machines/delete/<int:id>')
    @login_required
    def delete_machine(id):
        machine = Machine.query.get_or_404(id)
        db.session.delete(machine)
        db.session.commit()
        flash('تم حذف المكينة بنجاح', 'success')
        return redirect(url_for('machines_list'))

    # ==================== إدارة أنواع الأكياس ====================

    @app.route('/bag_types')
    @login_required
    def bag_types_list():
        bag_types = BagType.query.all()
        return render_template('bag_types.html', bag_types=bag_types)

    @app.route('/bag_types/add', methods=['POST'])
    @login_required
    def add_bag_type():
        bag_type = BagType(
            name=request.form.get('name'),
            size=request.form.get('size'),
            price_per_bag=float(request.form.get('price_per_bag')),
            is_active=request.form.get('is_active') == 'on'
        )
        db.session.add(bag_type)
        db.session.commit()
        flash('تم إضافة نوع الكيس بنجاح', 'success')
        return redirect(url_for('bag_types_list'))

    @app.route('/bag_types/edit/<int:id>', methods=['POST'])
    @login_required
    def edit_bag_type(id):
        bag_type = BagType.query.get_or_404(id)
        bag_type.name = request.form.get('name')
        bag_type.size = request.form.get('size')
        bag_type.price_per_bag = float(request.form.get('price_per_bag'))
        bag_type.is_active = request.form.get('is_active') == 'on'
        db.session.commit()
        flash('تم تحديث نوع الكيس بنجاح', 'success')
        return redirect(url_for('bag_types_list'))

    @app.route('/bag_types/delete/<int:id>')
    @login_required
    def delete_bag_type(id):
        bag_type = BagType.query.get_or_404(id)
        related = Production.query.filter_by(bag_type_id=id).count()
        if related > 0:
            flash(f'لا يمكن الحذف: مرتبط بـ {related} إنتاج', 'danger')
        else:
            db.session.delete(bag_type)
            db.session.commit()
            flash('تم الحذف بنجاح', 'success')
        return redirect(url_for('bag_types_list'))

    @app.route('/api/bag_type/<int:id>')
    @login_required
    def api_bag_type(id):
        bag_type = BagType.query.get_or_404(id)
        return jsonify({
            'success': True,
            'id': bag_type.id,
            'name': bag_type.name,
            'size': bag_type.size,
            'price_per_bag': bag_type.price_per_bag,
            'is_active': bag_type.is_active
        })

    # ==================== إدارة السلف ====================
    @app.route('/advances')
    @login_required
    def advances_list():
        advances = Advance.query.order_by(Advance.date.desc()).all()

        # جلب أسماء العاملات للقائمة المنسدلة
        machines = Machine.query.filter_by(is_active=True).all()

        # أسماء الخياطات الرئيسيات
        operators = [m.operator_name for m in machines if m.operator_name]

        # أسماء المساعدات الرسميات
        assistants = [m.assistant_name for m in machines if m.assistant_name]

        # أسماء العاملات المؤقتات من الإنتاج
        temp_workers = db.session.query(Production.worker_name).filter(
            Production.is_temporary == True,
            Production.worker_name.isnot(None)
        ).distinct().all()
        temp_workers = [w[0] for w in temp_workers if w[0]]

        # دمج جميع الأسماء للقائمة المنسدلة
        all_workers = list(set(operators + assistants + temp_workers))

        return render_template('advances.html',
                               advances=advances,
                               machines=machines,
                               temp_workers=temp_workers,
                               assistants=assistants,
                               datetime=datetime)

    @app.route('/advances/add', methods=['POST'])
    @login_required
    def add_advance():
        advance = Advance(
            worker_name=request.form.get('worker_name'),
            amount=float(request.form.get('amount')),
            date=datetime.strptime(request.form.get('date'), '%Y-%m-%d').date(),
            is_temporary=request.form.get('is_temporary') == 'on',
            notes=request.form.get('notes'),
            created_by=current_user.username
        )
        db.session.add(advance)
        db.session.flush()

        # إنشاء القيد المحاسبي
        AccountingSystem.create_advance_journal_entry(advance)

        flash('تم إضافة السلفة بنجاح', 'success')
        return redirect(url_for('advances_list'))

    @app.route('/advances/delete/<int:id>')
    @login_required
    def delete_advance(id):
        advance = Advance.query.get_or_404(id)
        db.session.delete(advance)
        db.session.commit()
        flash('تم حذف السلفة بنجاح', 'success')
        return redirect(url_for('advances_list'))

    # ==================== المستخلصات ====================

    @app.route('/settlements')
    @login_required
    def settlements_list():
        settlements = Settlement.query.order_by(Settlement.created_date.desc()).all()
        return render_template('settlements.html', settlements=settlements)

    @app.route('/settlements/create', methods=['GET', 'POST'])
    @login_required
    def create_settlement():
        bag_types = BagType.query.filter_by(is_active=True).all()

        if request.method == 'POST':
            start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
            end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
            settlement_type = request.form.get('settlement_type')
            selected_bag_ids = request.form.getlist('bag_type_ids')
            advance_to_contractor = float(request.form.get('advance_to_contractor', 0))

            if not selected_bag_ids:
                flash('الرجاء اختيار نوع واحد على الأقل من الأكياس', 'danger')
                return redirect(url_for('create_settlement'))

            selected_bag_ids = [int(x) for x in selected_bag_ids]

            # التحقق من عدم وجود مستخلص لنفس الفترة
            existing = Settlement.query.filter(
                ((start_date >= Settlement.start_date) & (start_date <= Settlement.end_date)) |
                ((end_date >= Settlement.start_date) & (end_date <= Settlement.end_date))
            ).first()

            if existing:
                flash(f'⚠️ لا يمكن إنشاء مستخلص! توجد فترة متداخلة من {existing.start_date} إلى {existing.end_date}',
                      'danger')
                return redirect(url_for('create_settlement'))

            # حساب إجمالي الإنتاج للأصناف المختارة
            productions = Production.query.filter(
                Production.date.between(start_date, end_date),
                Production.bag_type_id.in_(selected_bag_ids)
            ).all()

            total_production_amount = sum(p.total_amount for p in productions)
            total_quantity = sum(p.quantity for p in productions)
            # الحصول على الإعدادات
            settings = SystemSettings.query.first()

            # حساب التأمين والضريبة (نسب مئوية من إجمالي الإنتاج)
            total_insurance = total_production_amount * (settings.insurance_amount / 100) if settings else 0
            total_tax = total_production_amount * (settings.tax_amount / 100) if settings else 0

            # صافي المستحق للمتعهدة = إجمالي الإنتاج - التأمين - الضريبة - السلفة
            # (عمولة المتعهدة لا تخصم من المستخلص)
            net_amount = total_production_amount - total_insurance - total_tax - advance_to_contractor

            # ملاحظة: contractor_commission = 0 في المستخلص (لا تظهر)
            settlement = Settlement(
                start_date=start_date,
                end_date=end_date,
                settlement_type=settlement_type,
                total_production_amount=total_production_amount,
                total_quantity=total_quantity,
                total_insurance=total_insurance,
                total_tax=total_tax,
                advance_to_contractor=advance_to_contractor,
                net_amount=net_amount,
                created_by=current_user.username,
                status='draft'
            )
            db.session.add(settlement)
            db.session.flush()

            # ربط الأصناف
            for bag_id in selected_bag_ids:
                settlement_bag = SettlementBag(
                    settlement_id=settlement.id,
                    bag_type_id=bag_id
                )
                db.session.add(settlement_bag)

            db.session.commit()

            flash('تم إنشاء المستخلص بنجاح', 'success')
            return redirect(url_for('settlements_list'))

        return render_template('settlement_form.html', bag_types=bag_types)

    @app.route('/api/check-settlement-overlap')
    @login_required
    def check_settlement_overlap():
        """API للتحقق من تداخل الفترات"""
        from datetime import datetime

        start_date = datetime.strptime(request.args.get('start'), '%Y-%m-%d').date()
        end_date = datetime.strptime(request.args.get('end'), '%Y-%m-%d').date()

        # البحث عن مستخلصات متداخلة
        overlapping = Settlement.query.filter(
            # الفترة الجديدة تبدأ داخل فترة موجودة
            ((start_date >= Settlement.start_date) & (start_date <= Settlement.end_date)) |
            # الفترة الجديدة تنتهي داخل فترة موجودة
            ((end_date >= Settlement.start_date) & (end_date <= Settlement.end_date)) |
            # الفترة الجديدة تحتوي فترة موجودة بالكامل
            ((start_date <= Settlement.start_date) & (end_date >= Settlement.end_date))
        ).first()

        if overlapping:
            status_text = {
                'draft': 'مسودة',
                'posted': 'مرحل',
                'paid_to_contractor': 'تم الدفع للمتعهدة',
                'distributed': 'تم التوزيع'
            }.get(overlapping.status, overlapping.status)

            return jsonify({
                'has_overlap': True,
                'overlap_start': overlapping.start_date.strftime('%Y-%m-%d'),
                'overlap_end': overlapping.end_date.strftime('%Y-%m-%d'),
                'status': status_text
            })

        return jsonify({'has_overlap': False})

    @app.route('/settlements/post/<int:id>')
    @login_required
    def post_settlement(id):
        settlement = Settlement.query.get_or_404(id)
        settlement.status = 'posted'

        # تحديث القيد المحاسبي للمستخلص
        AccountingSystem.create_settlement_journal_entry(settlement)

        db.session.commit()
        flash('تم ترحيل المستخلص', 'success')
        return redirect(url_for('settlements_list'))

    # ==================== المحاسبة ====================

    @app.route('/accounts')
    @login_required
    def accounts_list():
        accounts = Account.query.order_by(Account.account_number).all()
        return render_template('accounts.html', accounts=accounts)

    @app.route('/journal_entries')
    @login_required
    def journal_entries():
        entries = JournalEntry.query.order_by(JournalEntry.date.desc()).all()
        return render_template('journal_entries.html', entries=entries)

    @app.route('/journal_entry/<int:id>')
    @login_required
    def journal_entry_detail(id):
        entry = JournalEntry.query.get_or_404(id)
        return render_template('journal_entry_detail.html', entry=entry)

    @app.route('/trial_balance')
    @login_required
    def trial_balance():
        result = AccountingSystem.get_trial_balance()
        return render_template('trial_balance.html',
                               trial_balance=result['accounts'],
                               total_debit=result['total_debit'],
                               total_credit=result['total_credit'],
                               is_balanced=result['is_balanced'])

    @app.route('/income_statement', methods=['GET', 'POST'])
    @login_required
    def income_statement():
        if request.method == 'POST':
            start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
            end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
            statement = AccountingSystem.get_income_statement(start_date, end_date)
            return render_template('income_statement.html', statement=statement)

        # الافتراضي: الشهر الحالي
        today = datetime.now().date()
        start_date = today.replace(day=1)
        end_date = today
        statement = AccountingSystem.get_income_statement(start_date, end_date)
        return render_template('income_statement.html', statement=statement)

    @app.route('/settlement/delete/<int:id>')
    @login_required
    def delete_settlement(id):
        settlement = Settlement.query.get_or_404(id)

        # لا يمكن حذف المستخلصات المرحلة أو المدفوعة
        if settlement.status != 'draft':
            flash('لا يمكن حذف مستخلص تم ترحيله أو دفعه', 'danger')
            return redirect(url_for('settlements_list'))

        db.session.delete(settlement)
        db.session.commit()
        flash('تم حذف المستخلص بنجاح', 'success')
        return redirect(url_for('settlements_list'))

    # ==================== إعدادات النظام ====================
    @app.route('/settings', methods=['GET', 'POST'])
    @login_required
    def settings():
        settings = SystemSettings.query.first()

        if request.method == 'POST':
            settings.contractor_amount = float(request.form.get('contractor_amount', 0))  # مبلغ ثابت
            settings.insurance_amount = float(request.form.get('insurance_amount', 0))
            settings.insurance_type = request.form.get('insurance_type', 'percentage')
            settings.tax_amount = float(request.form.get('tax_amount', 0))
            settings.tax_type = request.form.get('tax_type', 'percentage')
            settings.updated_by = current_user.username

            db.session.commit()
            flash('تم تحديث الإعدادات بنجاح', 'success')
            return redirect(url_for('settings'))

        return render_template('settings.html', settings=settings)

    # ==================== API للواجهة ====================

    @app.route('/api/stats')
    @login_required
    def api_stats():
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)

        daily_stats = db.session.query(
            Production.date,
            func.sum(Production.quantity).label('total_quantity'),
            func.sum(BagType.price_per_bag * Production.quantity).label('total_amount')
        ).join(BagType).filter(
            Production.date >= week_ago
        ).group_by(Production.date).all()

        return jsonify([{
            'date': str(stat.date),
            'quantity': stat.total_quantity,
            'amount': stat.total_amount
        } for stat in daily_stats])

    @app.route('/api/workers')
    @login_required
    def api_workers():
        # جلب جميع العاملات (من المكائن والمؤقتات)
        machine_workers = db.session.query(Machine.operator_name).filter(Machine.is_active == True).all()
        temp_workers = db.session.query(Production.worker_name).filter(Production.is_temporary == True,
                                                                       Production.worker_name.isnot(
                                                                           None)).distinct().all()

        workers = set([w[0] for w in machine_workers if w[0]] + [w[0] for w in temp_workers if w[0]])
        return jsonify(list(workers))

    # ==================== تقارير الخياطات ====================
    @app.route('/workers_report', methods=['GET', 'POST'])
    @login_required
    def workers_report():
        """تقرير تفصيلي للخياطات والمساعدات مع الكميات والأجور والسلف"""

        if request.method == 'POST':
            start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
            end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
            payment_method = request.form.get('payment_method', 'cash')
        else:
            # الافتراضي: الأسبوع الحالي
            today = datetime.now().date()
            start_date = today - timedelta(days=today.weekday())
            end_date = today
            payment_method = 'cash'

        # جلب جميع الخياطات الرئيسيات من المكائن
        machines = Machine.query.filter_by(is_active=True).all()

        # قائمة لتخزين جميع العاملات (خياطات + مساعدات)
        all_workers_dict = {}

        for m in machines:
            if m.operator_name:
                # إضافة خياطة رئيسية
                key = f"operator_{m.id}"
                if key not in all_workers_dict:
                    all_workers_dict[key] = {
                        'name': m.operator_name,
                        'type': 'permanent',
                        'sub_type': 'خياطة رئيسية',
                        'machine_id': m.id,
                        'machine_name': m.name,
                        'assistant_of': None
                    }

            if m.assistant_name:
                # إضافة مساعدة رسمية
                key = f"assistant_{m.id}"
                if key not in all_workers_dict:
                    all_workers_dict[key] = {
                        'name': m.assistant_name,
                        'type': 'permanent',
                        'sub_type': 'مساعدة رسمية',
                        'machine_id': m.id,
                        'machine_name': m.name,
                        'assistant_of': m.operator_name
                    }

        # جلب المساعدات المؤقتات من الإنتاج
        temp_assistants_list = db.session.query(Production.temporary_assistant).filter(
            Production.temporary_assistant.isnot(None),
            Production.temporary_assistant != '',
            Production.date.between(start_date, end_date)
        ).distinct().all()

        for ta in temp_assistants_list:
            if ta[0]:
                key = f"temp_{ta[0]}"
                if key not in all_workers_dict:
                    all_workers_dict[key] = {
                        'name': ta[0],
                        'type': 'temporary',
                        'sub_type': 'مساعدة مؤقتة',
                        'machine_id': None,
                        'machine_name': 'مؤقتة',
                        'assistant_of': None
                    }

        # جلب العاملات المؤقتات القديمات (من حقل worker_name) للتوافق مع البيانات القديمة
        temp_workers_list = db.session.query(Production.worker_name).filter(
            Production.is_temporary == True,
            Production.worker_name.isnot(None),
            Production.worker_name != '',
            Production.date.between(start_date, end_date)
        ).distinct().all()

        for tw in temp_workers_list:
            if tw[0]:
                key = f"temp_worker_{tw[0]}"
                if key not in all_workers_dict:
                    all_workers_dict[key] = {
                        'name': tw[0],
                        'type': 'temporary',
                        'sub_type': 'عاملة مؤقتة',
                        'machine_id': None,
                        'machine_name': 'مؤقتة',
                        'assistant_of': None
                    }

        # الحصول على إعدادات النظام
        settings = SystemSettings.query.first()

        workers_data = []
        total_workers_amount = 0

        # قائمة لتتبع العاملات التي تم دفعها في هذه الفترة (لمنع التكرار)
        from models import WorkerPayment
        paid_workers_in_period = set()
        payments_in_period = WorkerPayment.query.filter(
            WorkerPayment.payment_date.between(start_date, end_date)
        ).all()
        for p in payments_in_period:
            paid_workers_in_period.add(p.worker_name)

        for worker_key, worker in all_workers_dict.items():
            worker_name = worker['name']

            # التحقق إذا تم دفع هذا العاملة بالفعل في هذه الفترة (لمنع التكرار)
            if worker_name in paid_workers_in_period:
                continue

            # حساب إجمالي الإنتاج للعاملة
            productions = []

            if worker['sub_type'] == 'خياطة رئيسية':
                # إنتاج الخياطة الرئيسية = إنتاج مكينتها
                productions = Production.query.filter(
                    Production.date.between(start_date, end_date),
                    Production.machine_id == worker['machine_id']
                ).all()
            elif worker['sub_type'] == 'مساعدة رسمية':
                # إنتاج المساعدة الرسمية = إنتاج مكينتها (نفس الخياطة)
                productions = Production.query.filter(
                    Production.date.between(start_date, end_date),
                    Production.machine_id == worker['machine_id']
                ).all()
                # استبعاد الإنتاج الذي يحتوي على مساعدة مؤقتة
                productions = [p for p in productions if not p.temporary_assistant]
            elif worker['sub_type'] == 'مساعدة مؤقتة':
                # إنتاج المساعدة المؤقتة = الإنتاج الذي اسمه موجود في temporary_assistant
                productions = Production.query.filter(
                    Production.date.between(start_date, end_date),
                    Production.temporary_assistant == worker_name
                ).all()
            elif worker['sub_type'] == 'عاملة مؤقتة':
                # للتوافق مع البيانات القديمة
                productions = Production.query.filter(
                    Production.date.between(start_date, end_date),
                    Production.worker_name == worker_name
                ).all()

            if not productions:
                continue

            # حساب الإجماليات
            total_quantity = sum(p.quantity for p in productions)
            total_amount = sum(p.total_amount for p in productions)

            if total_quantity == 0:
                continue

            # حساب صافي الأجر للعاملة (نصف إنتاج المكينة للخياطة والمساعدة)
            if worker['sub_type'] in ['خياطة رئيسية', 'مساعدة رسمية', 'مساعدة مؤقتة']:
                # حساب خصومات المكينة كاملة ثم التوزيع 50%
                # نحتاج إلى حساب إجمالي إنتاج المكينة (قد يكون هناك أكثر من عاملة)
                machine_productions = Production.query.filter(
                    Production.date.between(start_date, end_date),
                    Production.machine_id == worker['machine_id']
                ).all() if worker['machine_id'] else productions

                machine_total_quantity = sum(p.quantity for p in machine_productions)
                machine_total_amount = sum(p.total_amount for p in machine_productions)

                contractor_commission = settings.contractor_amount * machine_total_quantity if settings else 0
                insurance = machine_total_amount * (
                            settings.insurance_amount / 100) if settings and settings.insurance_type == 'percentage' else (
                    settings.insurance_amount if settings else 0)
                tax = machine_total_amount * (
                            settings.tax_amount / 100) if settings and settings.tax_type == 'percentage' else (
                    settings.tax_amount if settings else 0)

                machine_net = machine_total_amount - contractor_commission - insurance - tax
                worker_share = machine_net / 2  # 50% لكل من الخياطة والمساعدة
            else:
                # للعاملات المؤقتات القديمات
                contractor_commission = settings.contractor_amount * total_quantity if settings else 0
                insurance = total_amount * (
                            settings.insurance_amount / 100) if settings and settings.insurance_type == 'percentage' else (
                    settings.insurance_amount if settings else 0)
                tax = total_amount * (
                            settings.tax_amount / 100) if settings and settings.tax_type == 'percentage' else (
                    settings.tax_amount if settings else 0)
                worker_share = total_amount - contractor_commission - insurance - tax

            # حساب السلف
            advances = Advance.query.filter(
                Advance.worker_name == worker_name,
                Advance.date.between(start_date, end_date),
                Advance.amount > 0
            ).all()
            total_advances = sum(a.amount for a in advances)

            # حساب الصافي
            net_amount = worker_share - total_advances

            # تفاصيل الإنتاج
            production_details = []
            for p in productions:
                production_details.append({
                    'date': p.date,
                    'bag_type': p.bag_type.full_name if p.bag_type else '-',
                    'quantity': p.quantity,
                    'amount': p.total_amount,
                    'machine': p.machine.name if p.machine else '-'
                })

            workers_data.append({
                'name': worker_name,
                'type': worker['sub_type'],
                'machine_name': worker['machine_name'],
                'productions': production_details,
                'total_quantity': total_quantity,
                'total_amount': total_amount,
                'worker_share': worker_share,
                'contractor_commission': contractor_commission,
                'insurance': insurance,
                'tax': tax,
                'advances': advances,
                'total_advances': total_advances,
                'net_amount': net_amount if net_amount > 0 else 0,
                'payment_method': payment_method
            })

            total_workers_amount += net_amount if net_amount > 0 else 0

        # ترتيب البيانات حسب الإجمالي
        workers_data.sort(key=lambda x: x['total_amount'], reverse=True)

        return render_template('workers_report.html',
                               workers=workers_data,
                               start_date=start_date,
                               end_date=end_date,
                               payment_method=payment_method,
                               total_workers_amount=total_workers_amount,
                               settings=settings)

    @app.route('/workers_report/print/<start_date>/<end_date>')
    @login_required
    def print_workers_report(start_date, end_date):
        """طباعة تقرير الخياطات"""
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()

        # نفس منطق التقرير أعلاه
        machines = Machine.query.filter_by(is_active=True).all()
        permanent_workers = [{'name': m.operator_name, 'type': 'permanent', 'machine_id': m.id, 'machine_name': m.name}
                             for m in machines if m.operator_name]

        temp_workers_list = db.session.query(Production.worker_name).filter(
            Production.is_temporary == True,
            Production.worker_name.isnot(None),
            Production.date.between(start, end)
        ).distinct().all()

        temp_workers = [{'name': w[0], 'type': 'temporary', 'machine_id': None, 'machine_name': 'مؤقتة'} for w in
                        temp_workers_list if w[0]]
        all_workers = permanent_workers + temp_workers

        settings = SystemSettings.query.first()

        workers_data = []
        for worker in all_workers:
            worker_name = worker['name']
            productions = Production.query.filter(Production.date.between(start, end),
                                                  Production.worker_name == worker_name).all()

            if worker['type'] == 'permanent' and worker['machine_id']:
                machine_productions = Production.query.filter(
                    Production.date.between(start, end),
                    Production.machine_id == worker['machine_id'],
                    Production.is_temporary == False
                ).all()
                productions.extend(machine_productions)

            total_quantity = sum(p.quantity for p in productions)
            total_amount = sum(p.total_amount for p in productions)

            contractor_commission = settings.contractor_amount * total_quantity if settings else 0

            insurance = total_amount * (
                        settings.insurance_amount / 100) if settings and settings.insurance_type == 'percentage' else (
                settings.insurance_amount if settings else 0)
            tax = total_amount * (settings.tax_amount / 100) if settings and settings.tax_type == 'percentage' else (
                settings.tax_amount if settings else 0)

            advances = Advance.query.filter(Advance.worker_name == worker_name, Advance.date.between(start, end)).all()
            total_advances = sum(a.amount for a in advances)
            net_amount = total_amount - contractor_commission - insurance - tax - total_advances

            workers_data.append({
                'name': worker_name,
                'total_quantity': total_quantity,
                'total_amount': total_amount,
                'contractor_commission': contractor_commission,
                'insurance': insurance,
                'tax': tax,
                'total_advances': total_advances,
                'net_amount': net_amount
            })

        return render_template('workers_report_print.html',
                               workers=workers_data,
                               start_date=start,
                               end_date=end,
                               settings=settings)

    @app.route('/workers_report/payment/<worker_name>/<amount>/<method>', methods=['POST'])
    @login_required
    def record_payment(worker_name, amount, method):
        """تسجيل دفع لأجور عاملة"""
        from datetime import datetime

        # يمكن إضافة جدول للمدفوعات إذا أردت
        # حالياً نقوم بتسجيل ملاحظة في السلف
        advance = Advance(
            worker_name=worker_name,
            amount=-float(amount),  # سالب يعني دفع
            date=datetime.now().date(),
            is_temporary=False,
            notes=f"دفع أجور عن طريق {method}",
            created_by=current_user.username
        )
        db.session.add(advance)
        db.session.commit()

        flash(f'تم تسجيل دفع مبلغ {amount} ريال للعاملة {worker_name}', 'success')
        return redirect(url_for('workers_report'))

    # ==================== نظام المدفوعات ====================

    @app.route('/settlement/payment/<int:settlement_id>', methods=['GET', 'POST'])
    @login_required
    def settlement_payment(settlement_id):
        """صفحة دفع المستخلص للشركة وتوزيعها على الخياطات"""
        from models import Payment, WorkerPayment, PaymentStatus

        settlement = Settlement.query.get_or_404(settlement_id)

        # جلب بيانات الخياطات للمستخلص
        start_date = settlement.start_date
        end_date = settlement.end_date

        # حساب بيانات الخياطات
        workers_data = calculate_workers_data(start_date, end_date)

        # جلب المدفوعات السابقة
        existing_payment = Payment.query.filter_by(settlement_id=settlement_id).first()

        if request.method == 'POST':
            action = request.form.get('action')

            if action == 'pay_contractor':
                # دفع المبلغ للمتعهدة
                payment_method = request.form.get('payment_method')
                reference_number = request.form.get('reference_number')
                amount = float(request.form.get('amount', settlement.net_amount))

                payment = Payment(
                    settlement_id=settlement_id,
                    amount=amount,
                    payment_date=datetime.now().date(),
                    payment_method=payment_method,
                    reference_number=reference_number,
                    status=PaymentStatus.PAID_TO_CONTRACTOR,
                    notes=f"تم دفع مبلغ المستخلص للمتعهدة - طريقة الدفع: {payment_method}",
                    created_by=current_user.username
                )
                db.session.add(payment)

                # تحديث حالة المستخلص
                settlement.status = 'paid_to_contractor'

                db.session.commit()

                # إنشاء قيد محاسبي للدفع
                create_payment_journal_entry(payment)

                flash(f'تم تسجيل دفع مبلغ {amount} ريال للمتعهدة بنجاح', 'success')
                return redirect(url_for('settlement_payment', settlement_id=settlement_id))

            elif action == 'distribute_to_workers':
                # توزيع المبالغ على الخياطات
                payment_id = request.form.get('payment_id')
                payment = Payment.query.get(payment_id)

                if not payment:
                    flash('لم يتم العثور على عملية الدفع', 'danger')
                    return redirect(url_for('settlement_payment', settlement_id=settlement_id))

                # تسجيل دفعات لكل عاملة
                for worker in workers_data:
                    worker_amount = float(request.form.get(f'amount_{worker["name"]}', 0))
                    if worker_amount > 0:
                        worker_payment = WorkerPayment(
                            payment_id=payment.id,
                            worker_name=worker['name'],
                            worker_type=worker['type'],
                            amount=worker_amount,
                            payment_date=datetime.now().date(),
                            payment_method=request.form.get(f'method_{worker["name"]}', 'cash'),
                            receipt_number=request.form.get(f'receipt_{worker["name"]}',
                                                            f'REC-{datetime.now().strftime("%Y%m%d")}-{worker["name"]}'),
                            notes=f'دفع أجور عن فترة {settlement.start_date} إلى {settlement.end_date}',
                            created_by=current_user.username
                        )
                        db.session.add(worker_payment)

                        # إضافة سلفة سالبة (تخفيض) للعاملة
                        advance = Advance(
                            worker_name=worker['name'],
                            amount=-worker_amount,  # سالب يعني دفع
                            date=datetime.now().date(),
                            is_temporary=(worker['type'] == 'temporary'),
                            notes=f'دفع أجور المستخلص رقم {settlement.id}',
                            created_by=current_user.username
                        )
                        db.session.add(advance)

                # تحديث حالة الدفع
                payment.status = PaymentStatus.DISTRIBUTED
                payment.notes += f" - تم توزيع المبلغ على {len([w for w in workers_data if float(request.form.get(f'amount_{w["name"]}', 0)) > 0])} عاملة"

                # تحديث حالة المستخلص
                settlement.status = 'distributed'

                db.session.commit()

                flash('تم توزيع المبالغ على الخياطات بنجاح', 'success')
                return redirect(url_for('settlement_payment', settlement_id=settlement_id))

        return render_template('settlement_payment.html',
                               settlement=settlement,
                               workers=workers_data,
                               payment=existing_payment)

    def calculate_workers_data(start_date, end_date):
        """حساب بيانات الخياطات لفترة محددة"""
        from models import Machine, Production, Advance, SystemSettings

        settings = SystemSettings.query.first()

        # جلب الخياطات الدائمات
        machines = Machine.query.filter_by(is_active=True).all()
        permanent_workers = [{'name': m.operator_name, 'type': 'permanent', 'machine_id': m.id, 'machine_name': m.name}
                             for m in machines if m.operator_name]

        # جلب الخياطات المؤقتات
        temp_workers_list = db.session.query(Production.worker_name).filter(
            Production.is_temporary == True,
            Production.worker_name.isnot(None),
            Production.date.between(start_date, end_date)
        ).distinct().all()

        temp_workers = [{'name': w[0], 'type': 'temporary', 'machine_id': None, 'machine_name': 'مؤقتة'}
                        for w in temp_workers_list if w[0]]

        all_workers = permanent_workers + temp_workers
        workers_data = []

        for worker in all_workers:
            worker_name = worker['name']

            # حساب الإنتاج
            productions = Production.query.filter(
                Production.date.between(start_date, end_date),
                Production.worker_name == worker_name
            ).all()

            if worker['type'] == 'permanent' and worker['machine_id']:
                machine_productions = Production.query.filter(
                    Production.date.between(start_date, end_date),
                    Production.machine_id == worker['machine_id'],
                    Production.is_temporary == False
                ).all()
                productions.extend(machine_productions)

            total_quantity = sum(p.quantity for p in productions)
            total_amount = sum(p.total_amount for p in productions)

            # حساب الخصومات
            contractor_commission = settings.contractor_amount * total_quantity if settings else 0
            insurance = total_amount * (
                        settings.insurance_amount / 100) if settings and settings.insurance_type == 'percentage' else (
                settings.insurance_amount if settings else 0)
            tax = total_amount * (settings.tax_amount / 100) if settings and settings.tax_type == 'percentage' else (
                settings.tax_amount if settings else 0)

            # حساب السلف
            advances = Advance.query.filter(
                Advance.worker_name == worker_name,
                Advance.date.between(start_date, end_date)
            ).all()
            total_advances = sum(a.amount for a in advances)

            # حساب الصافي
            net_amount = total_amount - contractor_commission - insurance - tax - total_advances

            workers_data.append({
                'name': worker_name,
                'type': worker['type'],
                'machine_name': worker['machine_name'],
                'total_quantity': total_quantity,
                'total_amount': total_amount,
                'contractor_commission': contractor_commission,
                'insurance': insurance,
                'tax': tax,
                'total_advances': total_advances,
                'net_amount': net_amount
            })

        # ترتيب حسب المبلغ
        workers_data.sort(key=lambda x: x['net_amount'], reverse=True)
        return workers_data

    def create_payment_journal_entry(payment):
        """إنشاء قيد محاسبي للدفع"""
        from accounting import AccountingSystem

        entries = [
            ('2000', payment.amount, 0.0, f"تسوية حساب المتعهدة - مستخلص رقم {payment.settlement_id}"),
            # مدين: دائنو المتعهدة
            ('1000', 0.0, payment.amount, f"صرف نقدي - طريقة الدفع {payment.payment_method}"),  # دائن: النقدية
        ]

        journal_entry = AccountingSystem.create_journal_entry(
            payment.payment_date,
            f"دفع مستخلص رقم {payment.settlement_id} للمتعهدة",
            entries,
            "PAY"
        )

        return journal_entry

    @app.route('/settlement/payment/receipt/<int:worker_payment_id>')
    @login_required
    def worker_payment_receipt(worker_payment_id):
        """طباعة إيصال دفع لعاملة"""
        from models import WorkerPayment

        worker_payment = WorkerPayment.query.get_or_404(worker_payment_id)
        return render_template('worker_payment_receipt.html', payment=worker_payment)

    @app.route('/api/settlement/workers/<int:settlement_id>')
    @login_required
    def api_settlement_workers(settlement_id):
        """API لجلب بيانات العاملات لمستخلص معين"""
        from models import Settlement

        settlement = Settlement.query.get_or_404(settlement_id)
        workers_data = calculate_workers_data(settlement.start_date, settlement.end_date)

        return jsonify(workers_data)

    @app.route('/settlement/receipts/<int:settlement_id>')
    @login_required
    def settlement_receipts(settlement_id):
        """عرض جميع إيصالات الدفع لمستخلص معين"""
        from models import Payment

        settlement = Settlement.query.get_or_404(settlement_id)
        payment = Payment.query.filter_by(settlement_id=settlement_id).first()

        if not payment:
            flash('لا توجد مدفوعات مسجلة لهذا المستخلص', 'warning')
            return redirect(url_for('settlements_list'))

        return render_template('settlement_receipts.html',
                               settlement=settlement,
                               payment=payment)

    @app.route('/worker_payment/sign/<int:worker_payment_id>', methods=['POST'])
    @login_required
    def sign_worker_payment(worker_payment_id):
        """تسجيل توقيع الخياطة على استلام المبلغ"""
        from models import WorkerPayment

        worker_payment = WorkerPayment.query.get_or_404(worker_payment_id)
        worker_payment.is_signed = True
        worker_payment.signature_date = datetime.now().date()

        db.session.commit()

        return jsonify({'success': True, 'message': 'تم تسجيل التوقيع بنجاح'})

    # ==================== التقارير المتقدمة ====================

    @app.route('/reports')
    @login_required
    def reports_page():
        """صفحة التقارير المتقدمة"""
        today = datetime.now().date()
        start_date = today.replace(day=1)
        return render_template('reports.html', start_date=start_date, end_date=today)

    @app.route('/api/report/<report_type>')
    @login_required
    def api_report(report_type):
        """API لتوليد التقارير"""
        start_date = datetime.strptime(request.args.get('start'), '%Y-%m-%d').date()
        end_date = datetime.strptime(request.args.get('end'), '%Y-%m-%d').date()

        data = {}

        if report_type == 'production_by_item':
            data = get_production_by_item_report(start_date, end_date)
        elif report_type == 'production_by_worker':
            data = get_production_by_worker_report(start_date, end_date)
        elif report_type == 'production_by_machine':
            data = get_production_by_machine_report(start_date, end_date)
        elif report_type == 'settlements':
            data = get_settlements_report(start_date, end_date)
        elif report_type == 'advances':
            data = get_advances_report(start_date, end_date)
        elif report_type == 'financial':
            data = get_financial_report(start_date, end_date)
        else:
            return jsonify({'success': False, 'message': 'نوع التقرير غير معروف'})

        return jsonify(data)

    def get_production_by_item_report(start_date, end_date):
        """تقرير الإنتاج حسب نوع الكيس"""
        productions = Production.query.filter(
            Production.date.between(start_date, end_date)
        ).all()

        items = {}
        for p in productions:
            name = p.bag_type.full_name if p.bag_type else 'غير محدد'
            if name not in items:
                items[name] = {'quantity': 0, 'amount': 0}
            items[name]['quantity'] += p.quantity
            items[name]['amount'] += p.total_amount

        total_quantity = sum(p.quantity for p in productions)
        total_amount = sum(p.total_amount for p in productions)

        items_list = []
        for name, data in items.items():
            percentage = (data['quantity'] / total_quantity * 100) if total_quantity > 0 else 0
            items_list.append({
                'name': name,
                'quantity': data['quantity'],
                'amount': data['amount'],
                'percentage': round(percentage, 1)
            })

        items_list.sort(key=lambda x: x['amount'], reverse=True)

        return {
            'success': True,
            'title': 'تقرير الإنتاج حسب نوع الكيس',
            'data': {
                'items': items_list,
                'total_quantity': total_quantity,
                'total_amount': total_amount
            }
        }

    def get_production_by_worker_report(start_date, end_date):
        """تقرير الإنتاج حسب العاملات"""
        productions = Production.query.filter(
            Production.date.between(start_date, end_date)
        ).all()

        settings = SystemSettings.query.first()
        contractor_rate = settings.contractor_amount if settings else 0

        workers = {}
        for p in productions:
            name = p.worker_name if p.worker_name else (p.machine.operator_name if p.machine else 'غير محدد')
            worker_type = 'مؤقتة' if p.is_temporary else 'دائمة'

            if name not in workers:
                workers[name] = {'type': worker_type, 'quantity': 0, 'amount': 0}

            workers[name]['quantity'] += p.quantity
            workers[name]['amount'] += p.total_amount

        total_quantity = sum(p.quantity for p in productions)
        workers_list = []
        total_commission = 0
        total_wage = 0
        total_net = 0

        for name, data in workers.items():
            commission = data['quantity'] * contractor_rate
            wage = data['amount']
            net = wage - commission

            workers_list.append({
                'name': name,
                'type': data['type'],
                'quantity': data['quantity'],
                'amount': data['amount'],
                'wage': wage,
                'commission': commission,
                'net': net
            })

            total_commission += commission
            total_wage += wage
            total_net += net

        workers_list.sort(key=lambda x: x['amount'], reverse=True)

        return {
            'success': True,
            'title': 'تقرير الإنتاج حسب العاملات',
            'data': {
                'workers': workers_list,
                'total_quantity': total_quantity,
                'total_amount': sum(p.total_amount for p in productions),
                'total_wage': total_wage,
                'total_commission': total_commission,
                'total_net': total_net
            }
        }

    def get_production_by_machine_report(start_date, end_date):
        """تقرير الإنتاج حسب المكينة"""
        productions = Production.query.filter(
            Production.date.between(start_date, end_date)
        ).all()

        machines = {}
        for p in productions:
            if not p.machine:
                continue
            name = p.machine.name
            operator = p.machine.operator_name or '-'

            if name not in machines:
                machines[name] = {'operator': operator, 'quantity': 0, 'amount': 0}

            machines[name]['quantity'] += p.quantity
            machines[name]['amount'] += p.total_amount

        total_quantity = sum(p.quantity for p in productions)
        total_amount = sum(p.total_amount for p in productions)

        machines_list = []
        for name, data in machines.items():
            percentage = (data['quantity'] / total_quantity * 100) if total_quantity > 0 else 0
            machines_list.append({
                'name': name,
                'operator': data['operator'],
                'quantity': data['quantity'],
                'amount': data['amount'],
                'percentage': round(percentage, 1)
            })

        machines_list.sort(key=lambda x: x['amount'], reverse=True)

        return {
            'success': True,
            'title': 'تقرير الإنتاج حسب المكينة',
            'data': {
                'machines': machines_list,
                'total_quantity': total_quantity,
                'total_amount': total_amount
            }
        }

    def get_settlements_report(start_date, end_date):
        """تقرير المستخلصات"""
        settlements = Settlement.query.filter(
            Settlement.created_date.between(start_date, end_date)
        ).all()

        settlements_list = []
        total_production = 0
        total_commission = 0
        total_insurance = 0
        total_tax = 0
        total_advances = 0
        total_net = 0

        for s in settlements:
            settlements_list.append({
                'start_date': s.start_date.strftime('%Y-%m-%d'),
                'end_date': s.end_date.strftime('%Y-%m-%d'),
                'type': s.settlement_type,
                'total_production': s.total_production_amount,
                'commission': s.contractor_commission,
                'insurance': s.total_insurance,
                'tax': s.total_tax,
                'advances': s.total_advances,
                'net': s.net_amount,
                'status': s.status
            })

            total_production += s.total_production_amount
            total_commission += s.contractor_commission
            total_insurance += s.total_insurance
            total_tax += s.total_tax
            total_advances += s.total_advances
            total_net += s.net_amount

        return {
            'success': True,
            'title': 'تقرير المستخلصات',
            'data': {
                'settlements': settlements_list,
                'total_production': total_production,
                'total_commission': total_commission,
                'total_insurance': total_insurance,
                'total_tax': total_tax,
                'total_advances': total_advances,
                'total_net': total_net
            }
        }

    def get_advances_report(start_date, end_date):
        """تقرير السلف"""
        advances = Advance.query.filter(
            Advance.date.between(start_date, end_date)
        ).all()

        advances_list = []
        total_amount = 0

        for a in advances:
            advances_list.append({
                'date': a.date.strftime('%Y-%m-%d'),
                'worker_name': a.worker_name,
                'amount': a.amount,
                'is_temporary': a.is_temporary,
                'notes': a.notes
            })
            total_amount += a.amount

        return {
            'success': True,
            'title': 'تقرير السلف',
            'data': {
                'advances': advances_list,
                'total_amount': total_amount
            }
        }

    def get_financial_report(start_date, end_date):
        """التقرير المالي"""
        from accounting import AccountingSystem

        statement = AccountingSystem.get_income_statement(start_date, end_date)

        return {
            'success': True,
            'title': 'الملخص المالي',
            'data': {
                'revenue': statement['total_revenue'],
                'expenses': statement['total_expenses'],
                'wages': statement['wages'],
                'commission': statement['commission'],
                'insurance': statement['insurance'],
                'tax': statement['tax'],
                'net_income': statement['net_income']
            }
        }

    # ==================== توزيع الأجور ====================
    @app.route('/distribute_salaries')
    @login_required
    def distribute_salaries():
        """صفحة توزيع الأجور"""
        today = datetime.now().date()
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        settlement_id = request.args.get('settlement_id')

        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            start_date = today.replace(day=1)

        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            end_date = today

        # جلب المستخلصات التي لم يتم توزيعها بعد (غير مرتبطة بمدفوعات العاملات)
        # نفحص المستخلصات التي حالتها posted أو paid_to_contractor ولم يتم صرف رواتب العاملات لها
        from models import WorkerPayment

        # جلب جميع المستخلصات المرحلة أو المدفوعة للمتعهدة
        all_settlements = Settlement.query.filter(
            Settlement.status.in_(['posted', 'paid_to_contractor'])
        ).order_by(Settlement.created_date.desc()).all()

        # تصفية المستخلصات التي لم يتم توزيع رواتب العاملات لها
        settlements = []
        for s in all_settlements:
            # التحقق إذا كان هناك مدفوعات للعاملات مرتبطة بهذا المستخلص
            # نفحص إذا كانت هناك مدفوعات في نفس فترة المستخلص
            payments_exist = WorkerPayment.query.filter(
                WorkerPayment.payment_date.between(s.start_date, s.end_date)
            ).first()

            if not payments_exist:
                settlements.append(s)

        settlement = None
        if settlement_id:
            settlement = Settlement.query.get(int(settlement_id))
            start_date = settlement.start_date
            end_date = settlement.end_date

        # حساب بيانات الخياطات والمساعدات
        workers_data = calculate_workers_and_assistants_for_distribution(start_date, end_date)
        total_net_amount = sum(w['net_amount'] for w in workers_data)

        # جلب آخر المدفوعات (آخر 20)
        recent_payments = WorkerPayment.query.order_by(WorkerPayment.payment_date.desc()).limit(20).all()

        return render_template('distribute_salaries.html',
                               workers_data=workers_data,
                               total_net_amount=total_net_amount,
                               start_date=start_date,
                               end_date=end_date,
                               settlements=settlements,
                               settlement=settlement,
                               recent_payments=recent_payments)

    def calculate_workers_and_assistants_for_distribution(start_date, end_date):
        """حساب بيانات الخياطات والمساعدات للتوزيع"""
        from models import Machine, Production, Advance, SystemSettings

        settings = SystemSettings.query.first()

        workers_data = []

        # جلب جميع المكائن النشطة
        machines = Machine.query.filter_by(is_active=True).all()

        for machine in machines:
            # حساب إنتاج المكينة في الفترة
            productions = Production.query.filter(
                Production.date.between(start_date, end_date),
                Production.machine_id == machine.id
            ).all()

            if not productions:
                continue

            total_quantity = sum(p.quantity for p in productions)
            total_amount = sum(p.total_amount for p in productions)

            # حساب عمولة المتعهدة (0.2 × عدد الأكياس)
            commission = settings.contractor_amount * total_quantity if settings else 0

            # حساب التأمينات والضرائب
            insurance = total_amount * (
                        settings.insurance_amount / 100) if settings and settings.insurance_type == 'percentage' else (
                settings.insurance_amount if settings else 0)
            tax = total_amount * (settings.tax_amount / 100) if settings and settings.tax_type == 'percentage' else (
                settings.tax_amount if settings else 0)

            # إجمالي الخصومات
            deductions = commission + insurance + tax
            net_payable = total_amount - deductions  # صافي اجر المكينة

            # توزيع 50% للخياطة و 50% للمساعدة
            operator_share = net_payable / 2
            assistant_share = net_payable / 2

            # حساب السلف للخياطة الرئيسية
            operator_advances = Advance.query.filter(
                Advance.worker_name == machine.operator_name,
                Advance.date.between(start_date, end_date),
                Advance.amount > 0
            ).all()
            operator_total_advances = sum(a.amount for a in operator_advances)

            # صافي الخياطة الرئيسية
            operator_net = operator_share - operator_total_advances

            # إضافة الخياطة الرئيسية (نوعها: خياطة رئيسية)
            workers_data.append({
                'name': machine.operator_name,
                'type': 'خياطة رئيسية',  # ✅ نوع صحيح
                'machine_name': machine.name,
                'total_quantity': total_quantity,
                'total_amount': total_amount,
                'commission': commission,
                'insurance': insurance,
                'tax': tax,
                'deductions': deductions,
                'operator_share': operator_share,
                'assistant_share': assistant_share,
                'total_advances': operator_total_advances,
                'net_amount': operator_net if operator_net > 0 else 0,
                'is_assistant': False
            })

            # تحديد اسم المساعدة (رسمية أو مؤقتة)
            temp_assistant = None
            for p in productions:
                if p.temporary_assistant:
                    temp_assistant = p.temporary_assistant
                    break

            if temp_assistant:
                assistant_name = temp_assistant
                assistant_type = 'مساعدة مؤقتة'  # ✅ نوع صحيح
            elif machine.assistant_name:
                assistant_name = machine.assistant_name
                assistant_type = 'مساعدة رسمية'  # ✅ نوع صحيح
            else:
                continue  # لا توجد مساعدة

            # حساب السلف للمساعدة
            assistant_advances = Advance.query.filter(
                Advance.worker_name == assistant_name,
                Advance.date.between(start_date, end_date),
                Advance.amount > 0
            ).all()
            assistant_total_advances = sum(a.amount for a in assistant_advances)

            # صافي المساعدة
            assistant_net = assistant_share - assistant_total_advances

            # إضافة المساعدة إلى القائمة
            workers_data.append({
                'name': assistant_name,
                'type': assistant_type,  # ✅ نوع صحيح
                'machine_name': machine.name,
                'total_quantity': total_quantity,
                'total_amount': total_amount,
                'commission': commission,
                'insurance': insurance,
                'tax': tax,
                'deductions': deductions,
                'operator_share': operator_share,
                'assistant_share': assistant_share,
                'total_advances': assistant_total_advances,
                'net_amount': assistant_net if assistant_net > 0 else 0,
                'is_assistant': True
            })

        # ترتيب حسب المبلغ
        workers_data.sort(key=lambda x: x['net_amount'], reverse=True)
        return workers_data

    @app.route('/api/distribute-salary', methods=['POST'])
    @login_required
    def api_distribute_salary():
        """API لتوزيع راتب خياطة واحدة"""
        from models import WorkerPayment
        from datetime import datetime

        data = request.get_json()
        worker_name = data.get('worker_name')
        amount = data.get('amount')
        payment_method = data.get('payment_method', 'cash')
        receipt_number = data.get('receipt_number')
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')

        if amount <= 0:
            return jsonify({'success': False, 'message': 'المبلغ يجب أن يكون أكبر من صفر'})

        # التحقق من وجود دفعة سابقة لنفس العاملة في نفس الفترة
        if start_date_str and end_date_str:
            start = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end = datetime.strptime(end_date_str, '%Y-%m-%d').date()

            # البحث عن دفعة سابقة
            existing_payment = WorkerPayment.query.filter(
                WorkerPayment.worker_name == worker_name,
                WorkerPayment.payment_date >= start,
                WorkerPayment.payment_date <= end
            ).first()

            if existing_payment:
                return jsonify({
                    'success': False,
                    'message': f'⚠️ لا يمكن الصرف مرتين! تم دفع مبلغ {existing_payment.amount:.2f} ريال للعاملة {worker_name} في هذه الفترة بالفعل'
                })

        # تسجيل الدفع
        worker_payment = WorkerPayment(
            worker_name=worker_name,
            amount=amount,
            payment_date=datetime.now().date(),
            payment_method=payment_method,
            receipt_number=receipt_number,
            created_by=current_user.username
        )
        db.session.add(worker_payment)
        db.session.commit()

        return jsonify({'success': True, 'message': 'تم تسجيل الدفع بنجاح'})

    @app.route('/api/distribute-all-salaries', methods=['POST'])
    @login_required
    def api_distribute_all_salaries():
        """API لتوزيع جميع الأجور مرة واحدة"""
        from models import WorkerPayment

        data = request.get_json()
        workers = data.get('workers', [])

        if not workers:
            return jsonify({'success': False, 'message': 'لا توجد بيانات للتوزيع'})

        for worker in workers:
            if worker['amount'] > 0:
                worker_payment = WorkerPayment(
                    worker_name=worker['name'],
                    amount=worker['amount'],
                    payment_date=datetime.now().date(),
                    payment_method=worker['method'],
                    receipt_number=worker.get('receipt'),
                    created_by=current_user.username
                )
                db.session.add(worker_payment)

        db.session.commit()

        return jsonify({'success': True, 'message': f'تم توزيع {len(workers)} دفعة بنجاح'})
