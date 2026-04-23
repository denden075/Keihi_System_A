from datetime import datetime, date
from sqlalchemy import Boolean, Integer, String, Text, Date, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    contact_person: Mapped[str | None] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String)
    phone: Mapped[str | None] = mapped_column(String)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    projects: Mapped[list["Project"]] = relationship("Project", back_populates="customer")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    project_number: Mapped[str | None] = mapped_column(String)
    order_number: Mapped[str | None] = mapped_column(String)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String, nullable=False, default="見積中")
    budget: Mapped[int | None] = mapped_column(Integer)
    sales_amount: Mapped[int | None] = mapped_column(Integer)
    accepted_year: Mapped[int | None] = mapped_column(Integer)
    accepted_month: Mapped[int | None] = mapped_column(Integer)
    customer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("customers.id"), nullable=True)
    probability: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    customer: Mapped["Customer | None"] = relationship("Customer", back_populates="projects")
    expenses: Mapped[list["Expense"]] = relationship(
        "Expense", back_populates="project", foreign_keys="Expense.project_id", cascade="all, delete-orphan"
    )

    @property
    def total_amount(self) -> int:
        return sum(e.amount_ex_tax for e in self.expenses)

    @property
    def net_sales(self) -> int | None:
        if self.sales_amount is None:
            return None
        return self.sales_amount - self.total_amount

    @property
    def is_over_budget(self) -> bool:
        return self.budget is not None and self.total_amount > self.budget

    @property
    def budget_remaining(self) -> int | None:
        if self.budget is None:
            return None
        return self.budget - self.total_amount

    @property
    def budget_usage_pct(self) -> float | None:
        if self.budget is None or self.budget == 0:
            return None
        return min(self.total_amount / self.budget * 100, 100)

    @property
    def accepted_label(self) -> str | None:
        if self.accepted_year and self.accepted_month:
            return f"{self.accepted_year}年{self.accepted_month}月"
        if self.accepted_year:
            return f"{self.accepted_year}年"
        return None


class Expense(Base):
    __tablename__ = "expenses"

    PAYMENT_METHODS = ["請求書", "クレジットカード"]
    ARRIVAL_STATUSES = ["未発注", "入着待ち", "入着済み"]

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False)
    origin_project_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("projects.id"), nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[int | None] = mapped_column(Integer)
    amount_ex_tax: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_inc_tax: Mapped[int | None] = mapped_column(Integer)
    issued_at: Mapped[date] = mapped_column(Date, nullable=False)
    invoice_processed_at: Mapped[date | None] = mapped_column(Date)
    arrival_date: Mapped[date | None] = mapped_column(Date)
    supplier: Mapped[str | None] = mapped_column(String)
    payment_method: Mapped[str | None] = mapped_column(String)
    order_number: Mapped[str | None] = mapped_column(String)
    person_in_charge: Mapped[str | None] = mapped_column(String)
    arrival_status: Mapped[str] = mapped_column(String, nullable=False, default="未発注")
    accounting_processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    project: Mapped["Project"] = relationship("Project", back_populates="expenses", foreign_keys="Expense.project_id")
    origin_project: Mapped["Project | None"] = relationship("Project", foreign_keys="Expense.origin_project_id")
