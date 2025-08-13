from sqlalchemy import create_engine, Column, Integer, String, Float, Text, Date, DateTime, Enum, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from typing import List, Optional
import enum

# 建立基底類別
Base = declarative_base()

# 定義枚舉類型
class CategoryType(enum.Enum):
    income = "income"
    expense = "expense"

# 定義 ORM 模型
class Category(Base):
    __tablename__ = 'categories'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    type = Column(Enum(CategoryType), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    
    # 關聯到交易
    transactions = relationship("Transaction", back_populates="category")
    
    # 唯一約束
    __table_args__ = (
        Index('unique_category', 'name', 'type', unique=True),
    )
    
    def __repr__(self):
        return f"<Category(id={self.id}, name='{self.name}', type='{self.type.value}')>"

class Transaction(Base):
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    amount = Column(Float, nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id', ondelete='SET NULL'))
    description = Column(Text)
    date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 關聯到分類
    category = relationship("Category", back_populates="transactions")
    
    # 索引
    __table_args__ = (
        Index('idx_date', 'date'),
        Index('idx_category', 'category_id'),
    )
    
    def __repr__(self):
        return f"<Transaction(id={self.id}, amount={self.amount}, date='{self.date}')>"

class ExpenseTrackerORM:
    def __init__(self, host='localhost', database='expense_tracker', user='root', password=''):
        """初始化記帳系統 - SQLAlchemy ORM 版本"""
        self.database_url = f"mysql+pymysql://{user}:{password}@{host}/{database}?charset=utf8mb4"
        self.engine = None
        self.Session = None
        self.init_database()

    def init_database(self):
        """初始化資料庫連線和資料表"""
        try:
            # 建立引擎
            self.engine = create_engine(
                self.database_url,
                echo=False,  # 設為 True 可以看到 SQL 語句
                pool_recycle=3600,
                pool_pre_ping=True
            )
            
            # 建立 Session 類別
            self.Session = sessionmaker(bind=self.engine)
            
            # 建立所有資料表
            Base.metadata.drop_all(self.engine)  # 清空舊資料表
            Base.metadata.create_all(self.engine)
            
            # 新增預設分類
            self._add_default_categories()
            
            print("✅ SQLAlchemy ORM 資料庫初始化完成！")
            
        except Exception as e:
            print(f"❌ 資料庫初始化失敗: {e}")

    def _add_default_categories(self):
        """新增預設分類"""
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
        
        session = self.Session()
        try:
            # 檢查是否已有分類，如果有就不新增
            existing_count = session.query(Category).count()
            if existing_count > 0:
                print("✅ 分類已存在，跳過新增預設分類")
                return
            
            # 如果沒有分類，才新增預設分類
            for name, cat_type in default_categories:
                category = Category(name=name, type=cat_type)
                session.add(category)
        
            # 在迴圈外面才 commit
            session.commit()
            print("✅ 預設分類新增完成！")
        
        except Exception as e:
            print(f"❌ 新增預設分類失敗: {e}")
            session.rollback()
        finally:
            session.close()

    def add_transaction(self, amount: float, category_id: int, description: str = "", date: str = None) -> bool:
        """新增交易記錄"""
        if date is None:
            date = datetime.now().date()
        else:
            date = datetime.strptime(date, "%Y-%m-%d").date()
        
        session = self.Session()
        try:
            transaction = Transaction(
                amount=amount,
                category_id=category_id,
                description=description,
                date=date
            )
            session.add(transaction)
            session.commit()
            print("✅ 交易記錄新增成功！")
            return True
            
        except Exception as e:
            print(f"❌ 新增交易失敗: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def get_categories(self, category_type: str = None) -> List[tuple]:
        """取得分類列表"""
        session = self.Session()
        try:
            query = session.query(Category)
            
            if category_type:
                cat_type = CategoryType.income if category_type == 'income' else CategoryType.expense
                query = query.filter(Category.type == cat_type)
            
            categories = query.order_by(Category.type, Category.name).all()
            
            # 轉換為元組格式以保持與原來的介面一致
            result = [(cat.id, cat.name, cat.type.value) for cat in categories]
            return result
            
        except Exception as e:
            print(f"❌ 取得分類失敗: {e}")
            return []
        finally:
            session.close()

    def get_transactions(self, limit: int = 10) -> List[tuple]:
        """取得交易記錄"""
        session = self.Session()
        try:
            transactions = (session.query(Transaction)
                          .join(Category, Transaction.category_id == Category.id, isouter=True)
                          .order_by(Transaction.date.desc(), Transaction.created_at.desc())
                          .limit(limit)
                          .all())
            
            # 轉換為元組格式
            result = []
            for trans in transactions:
                category_name = trans.category.name if trans.category else "未分類"
                category_type = trans.category.type.value if trans.category else "unknown"
                result.append((
                    trans.id,
                    trans.amount,
                    category_name,
                    category_type,
                    trans.description,
                    trans.date
                ))
            
            return result
            
        except Exception as e:
            print(f"❌ 取得交易記錄失敗: {e}")
            return []
        finally:
            session.close()
    
    def get_balance(self) -> dict:
        """計算總餘額"""
        session = self.Session()
        try:
            # 計算總收入
            total_income = (session.query(Transaction)
                          .join(Category)
                          .filter(Category.type == CategoryType.income)
                          .with_entities(Transaction.amount)
                          .all())
            total_income = sum(t.amount for t in total_income) if total_income else 0
            
            # 計算總支出
            total_expense = (session.query(Transaction)
                           .join(Category)
                           .filter(Category.type == CategoryType.expense)
                           .with_entities(Transaction.amount)
                           .all())
            total_expense = sum(t.amount for t in total_expense) if total_expense else 0
            
            return {
                'total_income': float(total_income),
                'total_expense': float(total_expense),
                'balance': float(total_income - total_expense)
            }
            
        except Exception as e:
            print(f"❌ 計算餘額失敗: {e}")
            return {'total_income': 0, 'total_expense': 0, 'balance': 0}
        finally:
            session.close()
    
    def delete_transaction(self, transaction_id: int) -> bool:
        """刪除交易記錄"""
        session = self.Session()
        try:
            transaction = session.query(Transaction).filter(Transaction.id == transaction_id).first()
            
            if transaction:
                session.delete(transaction)
                session.commit()
                print("✅ 交易記錄已刪除")
                return True
            else:
                print("❌ 找不到該交易記錄")
                return False
                
        except Exception as e:
            print(f"❌ 刪除失敗: {e}")
            session.rollback()
            return False
        finally:
            session.close()
    
    def add_category(self, name: str, category_type: str) -> bool:
        """新增分類"""
        if category_type not in ['income', 'expense']:
            print("❌ 分類類型無效，必須是 'income' 或 'expense'。")
            return False
        
        session = self.Session()
        try:
            cat_type = CategoryType.income if category_type == 'income' else CategoryType.expense
            category = Category(name=name, type=cat_type)
            session.add(category)
            session.commit()
            print(f"✅ 分類 '{name}' 新增成功！")
            return True
            
        except Exception as e:
            print(f"❌ 新增分類失敗: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def delete_category(self, category_id: int) -> bool:
        """刪除分類"""
        session = self.Session()
        try:
            category = session.query(Category).filter(Category.id == category_id).first()
            
            if category:
                session.delete(category)
                session.commit()
                print("✅ 分類已刪除")
                return True
            else:
                print("❌ 找不到該分類")
                return False
                
        except Exception as e:
            print(f"❌ 刪除分類失敗: {e}")
            session.rollback()
            return False
        finally:
            session.close()
    
    def display_categories(self):
        """顯示所有分類"""
        categories = self.get_categories()
        print("\n=== 分類列表 ===")
        income_cats = [cat for cat in categories if cat[2] == 'income']
        expense_cats = [cat for cat in categories if cat[2] == 'expense']
        
        print("💰 收入分類:")
        for cat in income_cats:
            print(f"  {cat[0]}. {cat[1]}")
        
        print("💸 支出分類:")
        for cat in expense_cats:
            print(f"  {cat[0]}. {cat[1]}")

    def display_transactions(self, limit: int = 10):
        """顯示交易記錄"""
        transactions = self.get_transactions(limit)
        if not transactions:
            print("❌ 沒有交易記錄")
            return
            
        print(f"\n=== 最近 {limit} 筆交易記錄 ===")
        print(f"{'ID':<4} {'金額':<12} {'分類':<12} {'類型':<6} {'描述':<20} {'日期'}")
        print("-" * 80)
        
        for trans in transactions:
            trans_id, amount, category, cat_type, description, date = trans
            type_symbol = "+" if cat_type == "income" else "-"
            amount_str = f"{type_symbol}{float(amount):.2f}"
            category = category or "未分類"
            description = description or ""
            print(f"{trans_id:<4} {amount_str:<12} {category:<12} {cat_type:<6} {description:<20} {date}")
    
    def display_balance(self):
        """顯示餘額資訊"""
        balance_info = self.get_balance()
        print(f"\n=== 💰 帳戶概況 ===")
        print(f"總收入: +{balance_info['total_income']:.2f}")
        print(f"總支出: -{balance_info['total_expense']:.2f}")
        print(f"{'='*20}")
        balance = balance_info['balance']
        balance_symbol = "💰" if balance >= 0 else "⚠️"
        print(f"餘額: {balance_symbol} {balance:.2f}")


def setup_database_connection():
    """設定資料庫連線參數"""
    print("=== MySQL 連線設定 ===")
    host = input("主機 (預設: localhost): ").strip() or 'localhost'
    database = input("資料庫名稱 (預設: expense_tracker): ").strip() or 'expense_tracker'
    user = input("使用者名稱 (預設: root): ").strip() or 'root'
    password = input("密碼: ").strip()
    
    return host, database, user, password


def main():
    """主程式"""
    print("🏦 歡迎使用記帳系統 (SQLAlchemy ORM版)")
    
    # 設定資料庫連線
    host, database, user, password = setup_database_connection()
    
    try:
        tracker = ExpenseTrackerORM(host, database, user, password)
    except Exception as e:
        print(f"❌ 初始化失敗: {e}")
        return
    
    while True:
        print("\n" + "="*40)
        print("🏦 記帳系統主選單")
        print("="*40)
        print("1. 💰 新增收入/支出")
        print("2. 📋 查看交易記錄") 
        print("3. 💳 查看帳戶餘額")
        print("4. 📁 查看分類")
        print("5. 🗑️  刪除交易記錄")
        print("0. 🚪 退出")
        print("="*40)
        
        choice = input("請選擇功能 (0-5): ").strip()
        
        if choice == "1":
            # 新增交易
            tracker.display_categories()
            try:
                category_id = int(input("\n請輸入分類ID: "))
                amount = float(input("請輸入金額: "))
                description = input("請輸入描述 (可選): ").strip()
                date_input = input("請輸入日期 (YYYY-MM-DD，直接按Enter使用今天): ").strip()
                
                date = date_input if date_input else None
                
                if tracker.add_transaction(amount, category_id, description, date):
                    print("✅ 交易記錄新增成功！")
                else:
                    print("❌ 交易記錄新增失敗！")
                    
            except ValueError:
                print("❌ 輸入格式錯誤！")
                
        elif choice == "2":
            try:
                limit = int(input("要顯示幾筆記錄？(預設10): ") or "10")
                tracker.display_transactions(limit)
            except ValueError:
                tracker.display_transactions()
                
        elif choice == "3":
            tracker.display_balance()
            
        elif choice == "4":
            tracker.display_categories()
            
        elif choice == "5":
            tracker.display_transactions()
            try:
                trans_id = int(input("\n請輸入要刪除的交易ID: "))
                confirm = input(f"確定要刪除交易 {trans_id} 嗎? (y/N): ").strip().lower()
                if confirm == 'y':
                    tracker.delete_transaction(trans_id)
            except ValueError:
                print("❌ 輸入格式錯誤！")
                
        elif choice == "0":
            print("👋 感謝使用記帳系統！")
            break
            
        else:
            print("❌ 無效的選擇，請重新輸入！")


if __name__ == "__main__":
    main()