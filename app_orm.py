# app_orm.py
from flask import Flask, render_template, request, redirect, url_for
from expense_tracker_sqlalchemy import ExpenseTrackerORM

app = Flask(__name__)

# 初始化 ExpenseTrackerORM
tracker = ExpenseTrackerORM(host='localhost', database='expense_tracker', user='root', password='123456')

@app.route('/')
def home():
    balance = tracker.get_balance()
    transactions = tracker.get_transactions(10)

    # 簡單計算收入與支出
    categories = tracker.get_categories()
    income_total = sum(t[1] for t in transactions if t[3] == 'income')
    expense_total = sum(t[1] for t in transactions if t[3] == 'expense')

    return render_template('index.html', 
                         balance=balance, 
                         transactions=transactions,
                         income_total=income_total,
                         expense_total=expense_total)

@app.route('/categories', methods=['GET', 'POST'])
def categories():
    if request.method == 'POST':
        name = request.form['name']
        category_type = request.form['type']
        tracker.add_category(name, category_type)
        return redirect(url_for('categories'))
    
    categories = tracker.get_categories()
    return render_template('categories.html', categories=categories)

@app.route('/delete_category/<int:cat_id>')
def delete_category(cat_id):
    tracker.delete_category(cat_id)
    return redirect(url_for('categories'))

@app.route('/add', methods=['GET', 'POST'])
def add_transaction():
    if request.method == 'POST':
        amount = float(request.form['amount'])
        category_id = int(request.form['category_id'])
        description = request.form.get('description', '')
        date = request.form.get('date', None)

        success = tracker.add_transaction(amount, category_id, description, date)
        if success:
            return redirect(url_for('home'))
        else:
            return "新增失敗", 500

    categories = tracker.get_categories()
    return render_template('add.html', categories=categories)

@app.route('/delete/<int:trans_id>')
def delete_transaction(trans_id):
    tracker.delete_transaction(trans_id)
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)