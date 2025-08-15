# app_orm.py
from flask import Flask, render_template, request, redirect, url_for, flash
from expense_tracker_sqlalchemy import ExpenseTrackerORM
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
import os

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "CHANGE_ME_TO_A_RANDOM_SECRET")

# === 初始化 ORM（依你的 MySQL 設定調整） ===
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'expense_tracker')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASS = os.getenv('DB_PASS')

tracker = ExpenseTrackerORM(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASS
)

# === Flask-Login 設定 ===
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class AuthUser(UserMixin):
    def __init__(self, uid: int, username: str):
        self.id = str(uid)
        self.username = username

@login_manager.user_loader
def load_user(user_id: str):
    u = tracker.get_user_by_id(int(user_id))
    return AuthUser(u['id'], u['username']) if u else None

# === Auth Routes ===
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password', '')
        ok, msg, user = tracker.create_user(username=username, password=password)
        if ok:
            login_user(AuthUser(user['id'], user['username']))
            flash('註冊並登入成功！', 'success')
            # 支援從受保護頁面被導來
            next_url = request.args.get('next') or url_for('home')
            return redirect(next_url)
        flash(msg, 'error')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password', '')
        user = tracker.verify_user(username, password)
        if user:
            login_user(AuthUser(user['id'], user['username']))
            flash('登入成功！', 'success')
            next_url = request.args.get('next') or url_for('home')
            return redirect(next_url)
        flash('帳號或密碼錯誤', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('你已登出', 'info')
    return redirect(url_for('login'))

# === 首頁 ===
@app.route('/')
@login_required
def home():
    uid = int(current_user.id)
    balance = tracker.get_balance(uid)
    transactions = tracker.get_transactions(uid, 10)

    # 若你想直接用統計，亦可：income_total = balance['total_income'] ...
    income_total = sum(t[1] for t in transactions if t[3] == 'income')
    expense_total = sum(t[1] for t in transactions if t[3] == 'expense')

    return render_template(
        'index.html',
        balance=balance,
        transactions=transactions,
        income_total=income_total,
        expense_total=expense_total
    )

# === 分類管理 ===
@app.route('/categories', methods=['GET', 'POST'])
@login_required
def categories():
    uid = int(current_user.id)
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        category_type = request.form.get('type')
        if name and category_type in ('income', 'expense'):
            tracker.add_category(uid, name, category_type)
        return redirect(url_for('categories'))
    cats = tracker.get_categories(uid)
    return render_template('categories.html', categories=cats)

@app.route('/delete_category/<int:cat_id>')
@login_required
def delete_category(cat_id: int):
    uid = int(current_user.id)
    tracker.delete_category(uid, cat_id)
    return redirect(url_for('categories'))

# === 新增交易 ===
@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_transaction():
    uid = int(current_user.id)
    if request.method == 'POST':
        amount = float(request.form.get('amount', 0) or 0)
        # 允許「未分類」
        cat_str = request.form.get('category_id', '')
        category_id = int(cat_str) if cat_str else None
        description = request.form.get('description', '') or ''
        date = request.form.get('date') or None

        success = tracker.add_transaction(uid, amount, category_id, description, date)
        if success:
            return redirect(url_for('home'))
        flash('新增失敗', 'error')

    cats = tracker.get_categories(uid)
    return render_template('add.html', categories=cats)

# === 刪除交易 ===
@app.route('/delete/<int:trans_id>')
@login_required
def delete_transaction(trans_id: int):
    uid = int(current_user.id)
    tracker.delete_transaction(uid, trans_id)
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)