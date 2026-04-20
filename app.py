import csv
import io
from collections import defaultdict
from datetime import date, datetime

from flask import Flask, render_template, request, redirect, url_for, flash, Response
from sqlalchemy import func, or_, nulls_last

import database
from database import init_db
from models import Customer, Project, Expense
from config import load_settings, save_settings, get_db_path

app = Flask(__name__)
app.secret_key = "keihi-app-secret"

STATUSES = ["見積中", "進行中", "完了", "失注"]


def get_db():
    return database.SessionLocal()


@app.template_filter("yen")
def yen_filter(value):
    if value is None:
        return "－"
    return f"¥{value:,}"


# ── ダッシュボード ──────────────────────────────────────────────────────────────

def _current_nendo() -> int:
    today = date.today()
    return today.year if today.month >= 4 else today.year - 1


def _nendo_months(nendo: int) -> list[tuple[int, int]]:
    months = [(nendo, m) for m in range(4, 13)]
    months += [(nendo + 1, m) for m in range(1, 4)]
    return months


@app.route("/")
def dashboard():
    db = get_db()
    try:
        projects = db.query(Project).all()
        total_projects = len(projects)
        active_projects = sum(1 for p in projects if p.status == "進行中")
        total_expense = sum(p.total_amount for p in projects)
        total_sales = sum(p.sales_amount for p in projects if p.sales_amount)
        total_net = total_sales - total_expense
        over_budget_count = sum(1 for p in projects if p.is_over_budget)

        top_projects = sorted(projects, key=lambda p: p.total_amount, reverse=True)[:5]

        # 年度別月次集計（3月決算）
        nendo = int(request.args.get("nendo", _current_nendo()))
        monthly_rows = []
        for year, month in _nendo_months(nendo):
            month_projects = [
                p for p in projects
                if p.accepted_year == year and p.accepted_month == month
            ]
            m_sales = sum(p.sales_amount or 0 for p in month_projects)
            m_expense = sum(p.total_amount for p in month_projects)
            monthly_rows.append({
                "year": year, "month": month,
                "sales": m_sales, "expense": m_expense,
                "net": m_sales - m_expense,
                "project_count": len(month_projects),
            })

        nendo_sales = sum(r["sales"] for r in monthly_rows)
        nendo_expense = sum(r["expense"] for r in monthly_rows)
        nendo_net = nendo_sales - nendo_expense

        # 年度セレクタ用（データがある年度を列挙 + 当年度）
        nendo_set = {_current_nendo()}
        for p in projects:
            if p.accepted_year and p.accepted_month:
                fy = p.accepted_year if p.accepted_month >= 4 else p.accepted_year - 1
                nendo_set.add(fy)
        nendo_list = sorted(nendo_set, reverse=True)

        return render_template(
            "dashboard.html",
            total_projects=total_projects,
            active_projects=active_projects,
            total_expense=total_expense,
            total_sales=total_sales,
            total_net=total_net,
            over_budget_count=over_budget_count,
            top_projects=top_projects,
            monthly_rows=monthly_rows,
            nendo=nendo,
            nendo_list=nendo_list,
            nendo_sales=nendo_sales,
            nendo_expense=nendo_expense,
            nendo_net=nendo_net,
        )
    finally:
        db.close()


# ── プロジェクト一覧 ────────────────────────────────────────────────────────────

@app.route("/projects")
def project_list():
    db = get_db()
    try:
        status_filters = request.args.getlist("status")   # 複数選択
        am_filters = request.args.getlist("am")           # "YYYY-M" 形式、複数選択
        sort = request.args.get("sort", "created_desc")

        query = db.query(Project)

        if status_filters:
            query = query.filter(Project.status.in_(status_filters))

        if am_filters:
            conds = []
            for am in am_filters:
                try:
                    y, m = am.split("-")
                    conds.append(
                        (Project.accepted_year == int(y)) & (Project.accepted_month == int(m))
                    )
                except ValueError:
                    pass
            if conds:
                query = query.filter(or_(*conds))

        if sort == "accepted_asc":
            query = query.order_by(
                nulls_last(Project.accepted_year.asc()),
                nulls_last(Project.accepted_month.asc()),
            )
        elif sort == "accepted_desc":
            query = query.order_by(
                nulls_last(Project.accepted_year.desc()),
                nulls_last(Project.accepted_month.desc()),
            )
        else:
            query = query.order_by(Project.created_at.desc())

        projects = query.all()

        # フィルタUI用：DBに存在する検収年月の一覧
        all_ym = db.query(Project.accepted_year, Project.accepted_month).filter(
            Project.accepted_year.isnot(None),
            Project.accepted_month.isnot(None),
        ).distinct().all()
        accepted_months = sorted({(y, m) for y, m in all_ym})

        return render_template(
            "projects/list.html",
            projects=projects,
            statuses=STATUSES,
            status_filters=status_filters,
            am_filters=am_filters,
            accepted_months=accepted_months,
            sort=sort,
        )
    finally:
        db.close()


# ── プロジェクト登録 ────────────────────────────────────────────────────────────

@app.route("/projects/new", methods=["GET", "POST"])
def project_new():
    db = get_db()
    try:
        customers = db.query(Customer).order_by(Customer.name).all()
        if request.method == "POST":
            budget_raw = request.form.get("budget", "").strip()
            sales_raw = request.form.get("sales_amount", "").strip()
            ay_raw = request.form.get("accepted_year", "").strip()
            am_raw = request.form.get("accepted_month", "").strip()
            cid_raw = request.form.get("customer_id", "").strip()
            project = Project(
                name=request.form["name"].strip(),
                description=request.form.get("description", "").strip() or None,
                project_number=request.form.get("project_number", "").strip() or None,
                order_number=request.form.get("order_number", "").strip() or None,
                start_date=date.fromisoformat(request.form["start_date"]),
                end_date=date.fromisoformat(request.form["end_date"]) if request.form.get("end_date") else None,
                status=request.form["status"],
                budget=int(budget_raw) if budget_raw else None,
                sales_amount=int(sales_raw) if sales_raw else None,
                accepted_year=int(ay_raw) if ay_raw else None,
                accepted_month=int(am_raw) if am_raw else None,
                customer_id=int(cid_raw) if cid_raw else None,
            )
            db.add(project)
            db.commit()
            flash("プロジェクトを登録しました。", "success")
            return redirect(url_for("project_detail", project_id=project.id))
        else:
            return render_template("projects/form.html", project=None, statuses=STATUSES, customers=customers)
    except Exception as e:
        db.rollback()
        flash(f"エラーが発生しました: {e}", "danger")
        return render_template("projects/form.html", project=None, statuses=STATUSES, customers=customers)
    finally:
        db.close()


# ── プロジェクト詳細 ────────────────────────────────────────────────────────────

@app.route("/projects/<int:project_id>")
def project_detail(project_id):
    db = get_db()
    try:
        project = db.get(Project, project_id)
        if not project:
            flash("プロジェクトが見つかりません。", "danger")
            return redirect(url_for("project_list"))

        date_from = request.args.get("date_from", "")
        date_to = request.args.get("date_to", "")

        expenses_query = db.query(Expense).filter(Expense.project_id == project_id)
        if date_from:
            expenses_query = expenses_query.filter(Expense.occurred_at >= date.fromisoformat(date_from))
        if date_to:
            expenses_query = expenses_query.filter(Expense.occurred_at <= date.fromisoformat(date_to))
        expenses = expenses_query.order_by(Expense.issued_at.desc()).all()

        category_totals = defaultdict(int)
        filtered_total = 0
        for e in expenses:
            category_totals[e.category] += e.amount
            filtered_total += e.amount

        return render_template(
            "projects/detail.html",
            project=project,
            expenses=expenses,
            category_totals=dict(category_totals),
            filtered_total=filtered_total,
            date_from=date_from,
            date_to=date_to,
        )
    finally:
        db.close()


# ── プロジェクト編集 ────────────────────────────────────────────────────────────

@app.route("/projects/<int:project_id>/edit", methods=["GET", "POST"])
def project_edit(project_id):
    db = get_db()
    try:
        project = db.get(Project, project_id)
        if not project:
            flash("プロジェクトが見つかりません。", "danger")
            return redirect(url_for("project_list"))

        customers = db.query(Customer).order_by(Customer.name).all()

        if request.method == "POST":
            budget_raw = request.form.get("budget", "").strip()
            sales_raw = request.form.get("sales_amount", "").strip()
            ay_raw = request.form.get("accepted_year", "").strip()
            am_raw = request.form.get("accepted_month", "").strip()
            cid_raw = request.form.get("customer_id", "").strip()
            project.name = request.form["name"].strip()
            project.description = request.form.get("description", "").strip() or None
            project.project_number = request.form.get("project_number", "").strip() or None
            project.order_number = request.form.get("order_number", "").strip() or None
            project.start_date = date.fromisoformat(request.form["start_date"])
            project.end_date = date.fromisoformat(request.form["end_date"]) if request.form.get("end_date") else None
            project.status = request.form["status"]
            project.budget = int(budget_raw) if budget_raw else None
            project.sales_amount = int(sales_raw) if sales_raw else None
            project.accepted_year = int(ay_raw) if ay_raw else None
            project.accepted_month = int(am_raw) if am_raw else None
            project.customer_id = int(cid_raw) if cid_raw else None
            db.commit()
            flash("プロジェクトを更新しました。", "success")
            return redirect(url_for("project_detail", project_id=project.id))

        return render_template("projects/form.html", project=project, statuses=STATUSES, customers=customers)
    except Exception as e:
        db.rollback()
        flash(f"エラーが発生しました: {e}", "danger")
        return redirect(url_for("project_list"))
    finally:
        db.close()


# ── プロジェクト削除 ────────────────────────────────────────────────────────────

@app.route("/projects/<int:project_id>/delete", methods=["POST"])
def project_delete(project_id):
    db = get_db()
    try:
        project = db.get(Project, project_id)
        if project:
            db.delete(project)
            db.commit()
            flash("プロジェクトを削除しました。", "success")
        return redirect(url_for("project_list"))
    except Exception as e:
        db.rollback()
        flash(f"エラーが発生しました: {e}", "danger")
        return redirect(url_for("project_list"))
    finally:
        db.close()


# ── 費用登録 ───────────────────────────────────────────────────────────────────

@app.route("/projects/<int:project_id>/expenses/new", methods=["GET", "POST"])
def expense_new(project_id):
    db = get_db()
    try:
        project = db.get(Project, project_id)
        if not project:
            flash("プロジェクトが見つかりません。", "danger")
            return redirect(url_for("project_list"))

        if request.method == "POST":
            expense = Expense(
                project_id=project_id,
                name=request.form["name"].strip(),
                category=request.form["category"],
                amount=int(request.form["amount"]),
                issued_at=date.fromisoformat(request.form["issued_at"]),
                received_at=date.fromisoformat(request.form["received_at"]) if request.form.get("received_at") else None,
                settlement=request.form["settlement"],
                note=request.form.get("note", "").strip() or None,
            )
            db.add(expense)
            db.commit()
            flash("費用を登録しました。", "success")
            return redirect(url_for("project_detail", project_id=project_id))

        return render_template(
            "expenses/form.html",
            project=project,
            expense=None,
            categories=Expense.CATEGORIES,
            settlements=Expense.SETTLEMENTS,
        )
    except Exception as e:
        db.rollback()
        flash(f"エラーが発生しました: {e}", "danger")
        return redirect(url_for("project_detail", project_id=project_id))
    finally:
        db.close()


# ── 費用編集 ───────────────────────────────────────────────────────────────────

@app.route("/projects/<int:project_id>/expenses/<int:expense_id>/edit", methods=["GET", "POST"])
def expense_edit(project_id, expense_id):
    db = get_db()
    try:
        project = db.get(Project, project_id)
        expense = db.get(Expense, expense_id)
        if not project or not expense or expense.project_id != project_id:
            flash("データが見つかりません。", "danger")
            return redirect(url_for("project_list"))

        if request.method == "POST":
            expense.name = request.form["name"].strip()
            expense.category = request.form["category"]
            expense.amount = int(request.form["amount"])
            expense.issued_at = date.fromisoformat(request.form["issued_at"])
            expense.received_at = date.fromisoformat(request.form["received_at"]) if request.form.get("received_at") else None
            expense.settlement = request.form["settlement"]
            expense.note = request.form.get("note", "").strip() or None
            db.commit()
            flash("費用を更新しました。", "success")
            return redirect(url_for("project_detail", project_id=project_id))

        return render_template(
            "expenses/form.html",
            project=project,
            expense=expense,
            categories=Expense.CATEGORIES,
            settlements=Expense.SETTLEMENTS,
        )
    except Exception as e:
        db.rollback()
        flash(f"エラーが発生しました: {e}", "danger")
        return redirect(url_for("project_detail", project_id=project_id))
    finally:
        db.close()


# ── 費用削除 ───────────────────────────────────────────────────────────────────

@app.route("/projects/<int:project_id>/expenses/<int:expense_id>/delete", methods=["POST"])
def expense_delete(project_id, expense_id):
    db = get_db()
    try:
        expense = db.get(Expense, expense_id)
        if expense and expense.project_id == project_id:
            db.delete(expense)
            db.commit()
            flash("費用を削除しました。", "success")
        return redirect(url_for("project_detail", project_id=project_id))
    except Exception as e:
        db.rollback()
        flash(f"エラーが発生しました: {e}", "danger")
        return redirect(url_for("project_detail", project_id=project_id))
    finally:
        db.close()


# ── 費用付け替え ────────────────────────────────────────────────────────────────

@app.route("/expenses/<int:expense_id>/reassign", methods=["GET", "POST"])
def expense_reassign(expense_id):
    db = get_db()
    try:
        expense = db.get(Expense, expense_id)
        if not expense:
            flash("費用が見つかりません。", "danger")
            return redirect(url_for("project_list"))

        original_project_id = expense.project_id

        if request.method == "POST":
            new_pid_raw = request.form.get("new_project_id", "").strip()
            if not new_pid_raw:
                flash("付け替え先プロジェクトを選択してください。", "danger")
                projects = db.query(Project).order_by(Project.name).all()
                return render_template(
                    "expenses/reassign.html",
                    expense=expense,
                    projects=projects,
                    original_project_id=original_project_id,
                )
            new_pid = int(new_pid_raw)
            if new_pid == original_project_id:
                flash("付け替え先が現在のプロジェクトと同じです。", "warning")
                return redirect(url_for("project_detail", project_id=original_project_id))
            target = db.get(Project, new_pid)
            if not target:
                flash("付け替え先プロジェクトが見つかりません。", "danger")
                return redirect(url_for("project_detail", project_id=original_project_id))
            expense.project_id = new_pid
            db.commit()
            flash(f"費用「{expense.name}」を「{target.name}」に付け替えました。", "success")
            return redirect(url_for("project_detail", project_id=new_pid))

        projects = db.query(Project).order_by(Project.name).all()
        return render_template(
            "expenses/reassign.html",
            expense=expense,
            projects=projects,
            original_project_id=original_project_id,
        )
    except Exception as e:
        db.rollback()
        flash(f"エラーが発生しました: {e}", "danger")
        return redirect(url_for("project_list"))
    finally:
        db.close()


# ── CSV出力 ────────────────────────────────────────────────────────────────────

@app.route("/projects/<int:project_id>/export")
def project_export(project_id):
    db = get_db()
    try:
        project = db.get(Project, project_id)
        if not project:
            flash("プロジェクトが見つかりません。", "danger")
            return redirect(url_for("project_list"))

        expenses = (
            db.query(Expense)
            .filter(Expense.project_id == project_id)
            .order_by(Expense.issued_at.desc())
            .all()
        )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["費用名", "カテゴリ", "金額（円）", "発行日", "領収日", "清算状況", "備考"])
        for e in expenses:
            writer.writerow([
                e.name, e.category, e.amount,
                e.issued_at.isoformat(),
                e.received_at.isoformat() if e.received_at else "",
                e.settlement,
                e.note or "",
            ])

        filename = f"{project.name}_費用一覧.csv"
        return Response(
            "\ufeff" + output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
        )
    finally:
        db.close()


# ── 顧客マスタ ─────────────────────────────────────────────────────────────────

@app.route("/customers")
def customer_list():
    db = get_db()
    try:
        customers = db.query(Customer).order_by(Customer.name).all()
        return render_template("customers/list.html", customers=customers)
    finally:
        db.close()


@app.route("/customers/new", methods=["GET", "POST"])
def customer_new():
    if request.method == "POST":
        db = get_db()
        try:
            customer = Customer(
                name=request.form["name"].strip(),
                contact_person=request.form.get("contact_person", "").strip() or None,
                email=request.form.get("email", "").strip() or None,
                phone=request.form.get("phone", "").strip() or None,
                note=request.form.get("note", "").strip() or None,
            )
            db.add(customer)
            db.commit()
            flash("顧客を登録しました。", "success")
            return redirect(url_for("customer_list"))
        except Exception as e:
            db.rollback()
            flash(f"エラーが発生しました: {e}", "danger")
        finally:
            db.close()

    return render_template("customers/form.html", customer=None)


@app.route("/customers/<int:customer_id>/edit", methods=["GET", "POST"])
def customer_edit(customer_id):
    db = get_db()
    try:
        customer = db.get(Customer, customer_id)
        if not customer:
            flash("顧客が見つかりません。", "danger")
            return redirect(url_for("customer_list"))

        if request.method == "POST":
            customer.name = request.form["name"].strip()
            customer.contact_person = request.form.get("contact_person", "").strip() or None
            customer.email = request.form.get("email", "").strip() or None
            customer.phone = request.form.get("phone", "").strip() or None
            customer.note = request.form.get("note", "").strip() or None
            db.commit()
            flash("顧客情報を更新しました。", "success")
            return redirect(url_for("customer_list"))

        return render_template("customers/form.html", customer=customer)
    except Exception as e:
        db.rollback()
        flash(f"エラーが発生しました: {e}", "danger")
        return redirect(url_for("customer_list"))
    finally:
        db.close()


@app.route("/customers/<int:customer_id>/delete", methods=["POST"])
def customer_delete(customer_id):
    db = get_db()
    try:
        customer = db.get(Customer, customer_id)
        if customer:
            for p in customer.projects:
                p.customer_id = None
            db.delete(customer)
            db.commit()
            flash("顧客を削除しました。", "success")
        return redirect(url_for("customer_list"))
    except Exception as e:
        db.rollback()
        flash(f"エラーが発生しました: {e}", "danger")
        return redirect(url_for("customer_list"))
    finally:
        db.close()


# ── 設定 ───────────────────────────────────────────────────────────────────────

@app.route("/settings", methods=["GET", "POST"])
def settings():
    import os
    settings_data = load_settings()

    if request.method == "POST":
        new_path = request.form.get("db_path", "").strip()
        if not new_path:
            flash("ファイルパスを入力してください。", "danger")
            return redirect(url_for("settings"))

        new_path = os.path.normpath(new_path)
        parent_dir = os.path.dirname(new_path)
        if parent_dir and not os.path.isdir(parent_dir):
            flash(f"ディレクトリが存在しません: {parent_dir}", "danger")
            return redirect(url_for("settings"))

        save_settings({"db_path": new_path})
        database.reconfigure(new_path)
        flash(f"データベースを切り替えました: {new_path}", "success")
        return redirect(url_for("settings"))

    import os
    current_path = os.path.abspath(settings_data.get("db_path", "keihi.db"))
    db_exists = os.path.isfile(current_path)
    db_size = os.path.getsize(current_path) if db_exists else None

    return render_template(
        "settings.html",
        current_path=current_path,
        db_exists=db_exists,
        db_size=db_size,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
