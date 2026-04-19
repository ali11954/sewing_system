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
            worker_name = request.form.get('worker_name')
            is_temporary = request.form.get('is_temporary') == 'on'
            notes = request.form.get('notes')

            # ========== التحقق من عدم وجود إنتاج مكرر ==========
            existing = Production.query.filter(
                Production.date == date,
                Production.machine_id == machine_id,
                Production.bag_type_id == bag_type_id
            ).first()

            if existing:
                flash(f'⚠️ لا يمكن إضافة إنتاج مكرر! يوجد إنتاج سابق لنفس المكينة ونفس نوع الكيس في هذا اليوم',
                      'danger')
                return redirect(url_for('add_production'))
            # =================================================

            production = Production(
                date=date,
                machine_id=machine_id,
                bag_type_id=bag_type_id,
                quantity=quantity,
                worker_name=worker_name,
                is_temporary=is_temporary,
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
            production.worker_name = request.form.get('worker_name')
            production.is_temporary = request.form.get('is_temporary') == 'on'
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
        machine.is_active = request.form.get('is_active') == 'on'
        db.session.commit()
        flash('تم تحديث المكينة بنجاح', 'success')
        return redirect(url_for('machines_list'))

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
        temp_workers = db.session.query(Production.worker_name).filter(
            Production.is_temporary == True,
            Production.worker_name.isnot(None)
        ).distinct().all()
        temp_workers = [w[0] for w in temp_workers if w[0]]

        return render_template('advances.html',
                               advances=advances,
                               machines=machines,
                               temp_workers=temp_workers,
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
        if request.method == 'POST':
            start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
            end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
            settlement_type = request.form.get('settlement_type')

            # ========== التحقق من عدم وجود مستخلص بنفس الفترة ==========
            # التحقق من وجود مستخلص يتداخل مع الفترة المطلوبة
            overlapping = Settlement.query.filter(
                # حالة 1: الفترة الجديدة تبدأ داخل فترة موجودة
                ((start_date >= Settlement.start_date) & (start_date <= Settlement.end_date)) |
                # حالة 2: الفترة الجديدة تنتهي داخل فترة موجودة
                ((end_date >= Settlement.start_date) & (end_date <= Settlement.end_date)) |
                # حالة 3: الفترة الجديدة تحتوي فترة موجودة بالكامل
                ((start_date <= Settlement.start_date) & (end_date >= Settlement.end_date))
            ).first()

            if overlapping:
                flash(
                    f'⚠️ لا يمكن إنشاء مستخلص! توجد فترة متداخلة من {overlapping.start_date} إلى {overlapping.end_date}',
                    'danger')
                return redirect(url_for('create_settlement'))

            # التحقق من وجود مستخلص بنفس التواريخ تماماً
            exact_match = Settlement.query.filter_by(
                start_date=start_date,
                end_date=end_date
            ).first()

            if exact_match:
                flash(f'⚠️ لا يمكن إنشاء مستخلص! يوجد مستخلص سابق لنفس الفترة {start_date} إلى {end_date}', 'danger')
                return redirect(url_for('create_settlement'))

            # ========== باقي الكود الأصلي ==========
            # حساب إجمالي الإنتاج في الفترة
            productions = Production.query.filter(
                Production.date.between(start_date, end_date)
            ).all()

            total_production_amount = sum(p.total_amount for p in productions)

            # حساب السلف في الفترة
            advances = Advance.query.filter(
                Advance.date.between(start_date, end_date),
                Advance.amount > 0  # فقط السلف الموجبة
            ).all()
            total_advances = sum(a.amount for a in advances)

            # الحصول على الإعدادات
            settings = SystemSettings.query.first()
            contractor_commission = total_production_amount * (settings.contractor_percentage / 100) if settings else 0
            total_insurance = total_production_amount * (
                        settings.insurance_amount / 100) if settings and settings.insurance_type == 'percentage' else (
                settings.insurance_amount if settings else 0)
            total_tax = total_production_amount * (
                        settings.tax_amount / 100) if settings and settings.tax_type == 'percentage' else (
                settings.tax_amount if settings else 0)

            net_amount = total_production_amount - contractor_commission - total_insurance - total_tax - total_advances

            settlement = Settlement(
                start_date=start_date,
                end_date=end_date,
                settlement_type=settlement_type,
                total_production_amount=total_production_amount,
                contractor_commission=contractor_commission,
                total_insurance=total_insurance,
                total_tax=total_tax,
                total_advances=total_advances,
                net_amount=net_amount,
                created_by=current_user.username,
                status='draft'
            )
            db.session.add(settlement)
            db.session.commit()

            flash('تم إنشاء المستخلص بنجاح', 'success')
            return redirect(url_for('settlements_list'))

        return render_template('settlement_form.html')

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

        # إنشاء القيد المحاسبي
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
            settings.contractor_percentage = float(request.form.get('contractor_percentage', 0))
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
        """تقرير تفصيلي للخياطات مع الكميات والأجور والسلف"""

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

        # جلب جميع الخياطات (من المكائن)
        machines = Machine.query.filter_by(is_active=True).all()
        permanent_workers = [{'name': m.operator_name, 'type': 'permanent', 'machine_id': m.id, 'machine_name': m.name}
                             for m in machines if m.operator_name]

        # جلب الخياطات المؤقتات من الإنتاج
        temp_workers_list = db.session.query(Production.worker_name).filter(
            Production.is_temporary == True,
            Production.worker_name.isnot(None),
            Production.date.between(start_date, end_date)
        ).distinct().all()

        temp_workers = [{'name': w[0], 'type': 'temporary', 'machine_id': None, 'machine_name': 'مؤقتة'} for w in
                        temp_workers_list if w[0]]

        all_workers = permanent_workers + temp_workers

        # الحصول على إعدادات النظام
        settings = SystemSettings.query.first()

        workers_data = []
        total_workers_amount = 0

        for worker in all_workers:
            worker_name = worker['name']

            # حساب إجمالي الإنتاج للعاملة
            productions = Production.query.filter(
                Production.date.between(start_date, end_date),
                Production.worker_name == worker_name
            ).all()

            # إذا كانت عاملة دائمة، نشمل إنتاج مكينتها أيضاً
            if worker['type'] == 'permanent' and worker['machine_id']:
                machine_productions = Production.query.filter(
                    Production.date.between(start_date, end_date),
                    Production.machine_id == worker['machine_id'],
                    Production.is_temporary == False
                ).all()
                productions.extend(machine_productions)

            # حساب الإجماليات
            total_quantity = sum(p.quantity for p in productions)
            total_amount = sum(p.total_amount for p in productions)

            # حساب الخصومات
            contractor_commission = total_amount * (settings.contractor_percentage / 100) if settings else 0
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
                'type': worker['type'],
                'machine_name': worker['machine_name'],
                'productions': production_details,
                'total_quantity': total_quantity,
                'total_amount': total_amount,
                'contractor_commission': contractor_commission,
                'insurance': insurance,
                'tax': tax,
                'advances': advances,
                'total_advances': total_advances,
                'net_amount': net_amount,
                'payment_method': payment_method
            })

            total_workers_amount += net_amount

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

            contractor_commission = total_amount * (settings.contractor_percentage / 100) if settings else 0
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
            contractor_commission = total_amount * (settings.contractor_percentage / 100) if settings else 0
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