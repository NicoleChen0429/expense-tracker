from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Text, Date, DateTime,
    Enum, ForeignKey, Index, UniqueConstraint, func
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from typing import List, Optional, Tuple, Dict
from werkzeug.security import generate_password_hash, check_password_hash
import enum

# 建立基底類別
Base = declarative_base()

# 定義枚舉類型
class CategoryType(enum.Enum):
    income = "income"
    expense = "expense"

# 使用者（僅 username，無 email）
class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    categories = relationship("Category", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"

# 分類
class Category(Base):
    __tablename__ = 'categories'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    name = Column(String(100), nullable=False)
    type = Column(Enum(CategoryType), nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    user = relationship("User", back_populates="categories")
    transactions = relationship("Transaction", back_populates="category")

    __table_args__ = (
        # 同一位使用者底下，name+type 不可重覆
        UniqueConstraint('user_id', 'name', 'type', name='uq_user_category'),
        Index('idx_cat_user', 'user_id'),
    )

    def __repr__(self):
        return f"<Category(id={self.id}, user_id={self.user_id}, name='{self.name}', type='{self.type.value}')>"

# 交易
class Transaction(Base):
    __tablename__ = 'transactions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    amount = Column(Float, nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id', ondelete='SET NULL'))
    description = Column(Text)
    date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    user = relationship("User", back_populates="transactions")
    category = relationship("Category", back_populates="transactions")

    __table_args__ = (
        Index('idx_trans_user', 'user_id'),
        Index('idx_trans_date', 'date'),
        Index('idx_trans_category', 'category_id'),
    )

    def __repr__(self):
        return f"<Transaction(id={self.id}, user_id={self.user_id}, amount={self.amount}, date='{self.date}')>"

class ExpenseTrackerORM:
    def __init__(self, host='localhost', database='expense_tracker', user='root', password=''):
        """初始化記帳系統 - SQLAlchemy ORM 版本（含使用者與資料隔離）"""
        self.database_url = f"mysql+pymysql://{user}:{password}@{host}/{database}?charset=utf8mb4"
        self.engine = None
        self.Session = None
        self.init_database()

    # === 初始化 ===
    def init_database(self):
        try:
            self.engine = create_engine(
                self.database_url,
                echo=False,
                pool_recycle=3600,
                pool_pre_ping=True
            )
            self.Session = sessionmaker(bind=self.engine)

            # 只建立不存在的資料表，**不要** drop_all()
            Base.metadata.create_all(self.engine)
            print("✅ SQLAlchemy ORM 資料庫初始化完成！")
        except Exception as e:
            print(f"❌ 資料庫初始化失敗: {e}")

    # === 使用者 ===
    def create_user(self, username: str, password: str) -> Tuple[bool, str, Optional[Dict]]:
        """用 username 建立帳號；回傳 (ok, msg, user_dict)"""
        session = self.Session()
        try:
            username = (username or "").strip()
            if not username:
                return False, "帳號 ID 不可為空", None

            # 檢查帳號是否重複
            if session.query(User).filter(User.username == username).first():
                return False, "帳號 ID 已被使用", None

            user = User(username=username, password_hash=generate_password_hash(password))
            session.add(user)
            session.commit()  # 取得 user.id

            self._add_default_categories_for_user(session, user.id)
            session.commit()
            return True, "註冊成功", {"id": user.id, "username": user.username}
        except Exception as e:
            session.rollback()
            return False, f"建立用戶失敗: {e}", None
        finally:
            session.close()

    def _add_default_categories_for_user(self, session, user_id: int):
        default_categories = [
            ('薪水', CategoryType.income),
            ('投資收入', CategoryType.income),
            ('其他收入', CategoryType.income),
            ('餐費', CategoryType.expense),
            ('交通', CategoryType.expense),
            ('娛樂', CategoryType.expense),
            ('購物', CategoryType.expense),
            ('生活用品', CategoryType.expense),
            ('醫療', CategoryType.expense),
            ('其他支出', CategoryType.expense)
        ]
        for name, cat_type in default_categories:
            session.add(Category(user_id=user_id, name=name, type=cat_type))

    def verify_user(self, username: str, password: str) -> Optional[Dict]:
        """用 username + 密碼登入"""
        session = self.Session()
        try:
            u = session.query(User).filter(User.username == (username or "").strip()).first()
            if u and check_password_hash(u.password_hash, password):
                return {"id": u.id, "username": u.username}
            return None
        finally:
            session.close()

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """依 id 取使用者（給 Flask-Login 用）"""
        session = self.Session()
        try:
            u = session.query(User).filter(User.id == user_id).first()
            if not u:
                return None
            return {"id": u.id, "username": u.username}
        finally:
            session.close()

    # === 分類 ===
    def get_categories(self, user_id: int, category_type: Optional[str] = None) -> List[tuple]:
        session = self.Session()
        try:
            query = session.query(Category).filter(Category.user_id == user_id)
            if category_type:
                cat_type = CategoryType.income if category_type == 'income' else CategoryType.expense
                query = query.filter(Category.type == cat_type)
            categories = query.order_by(Category.type, Category.name).all()
            return [(cat.id, cat.name, cat.type.value) for cat in categories]
        except Exception as e:
            print(f"❌ 取得分類失敗: {e}")
            return []
        finally:
            session.close()

    def add_category(self, user_id: int, name: str, category_type: str) -> bool:
        if category_type not in ['income', 'expense']:
            print("❌ 分類類型無效，必須是 'income' 或 'expense'。")
            return False
        session = self.Session()
        try:
            cat_type = CategoryType.income if category_type == 'income' else CategoryType.expense
            category = Category(user_id=user_id, name=name, type=cat_type)
            session.add(category)
            session.commit()
            return True
        except Exception as e:
            print(f"❌ 新增分類失敗: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def delete_category(self, user_id: int, category_id: int) -> bool:
        session = self.Session()
        try:
            category = (
                session.query(Category)
                .filter(Category.id == category_id, Category.user_id == user_id)
                .first()
            )
            if category:
                session.delete(category)
                session.commit()
                return True
            return False
        except Exception as e:
            print(f"❌ 刪除分類失敗: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    # === 交易 ===
    def add_transaction(
        self, user_id: int, amount: float, category_id: Optional[int],
        description: str = "", date: Optional[str] = None
    ) -> bool:
        if date is None:
            date_obj = datetime.now().date()
        else:
            date_obj = datetime.strptime(date, "%Y-%m-%d").date()
        session = self.Session()
        try:
            # 確認分類屬於該用戶
            category = None
            if category_id:
                category = (
                    session.query(Category)
                    .filter(Category.id == category_id, Category.user_id == user_id)
                    .first()
                )
                if not category:
                    print("❌ 分類不屬於該用戶或不存在")
                    return False

            transaction = Transaction(
                user_id=user_id,
                amount=amount,
                category_id=category_id if category else None,
                description=description,
                date=date_obj,
            )
            session.add(transaction)
            session.commit()
            return True
        except Exception as e:
            print(f"❌ 新增交易失敗: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def get_transactions(self, user_id: int, limit: int = 10) -> List[tuple]:
        session = self.Session()
        try:
            transactions = (
                session.query(Transaction)
                .filter(Transaction.user_id == user_id)
                .join(Category, Transaction.category_id == Category.id, isouter=True)
                .order_by(Transaction.date.desc(), Transaction.created_at.desc())
                .limit(limit)
                .all()
            )
            result = []
            for trans in transactions:
                category_name = trans.category.name if trans.category else "未分類"
                category_type = trans.category.type.value if trans.category else "unknown"
                result.append((
                    trans.id,
                    trans.amount,
                    category_name,
                    category_type,
                    trans.description or "",
                    trans.date
                ))
            return result
        except Exception as e:
            print(f"❌ 取得交易記錄失敗: {e}")
            return []
        finally:
            session.close()

    def get_balance(self, user_id: int) -> dict:
        session = self.Session()
        try:
            income_sum = (
                session.query(func.sum(Transaction.amount))
                .join(Category, Transaction.category_id == Category.id)
                .filter(Transaction.user_id == user_id, Category.type == CategoryType.income)
                .scalar() or 0.0
            )
            expense_sum = (
                session.query(func.sum(Transaction.amount))
                .join(Category, Transaction.category_id == Category.id)
                .filter(Transaction.user_id == user_id, Category.type == CategoryType.expense)
                .scalar() or 0.0
            )
            return {
                'total_income': float(income_sum),
                'total_expense': float(expense_sum),
                'balance': float(income_sum - expense_sum)
            }
        except Exception as e:
            print(f"❌ 計算餘額失敗: {e}")
            return {'total_income': 0, 'total_expense': 0, 'balance': 0}
        finally:
            session.close()

    def delete_transaction(self, user_id: int, transaction_id: int) -> bool:
        session = self.Session()
        try:
            transaction = (
                session.query(Transaction)
                .filter(Transaction.id == transaction_id, Transaction.user_id == user_id)
                .first()
            )
            if transaction:
                session.delete(transaction)
                session.commit()
                return True
            return False
        except Exception as e:
            print(f"❌ 刪除失敗: {e}")
            session.rollback()
            return False
        finally:
            session.close()