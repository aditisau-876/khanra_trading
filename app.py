from dotenv import load_dotenv
import os
load_dotenv(override=True)
from flask import Flask, render_template, request, jsonify
from sqlalchemy import create_engine, text
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib import colors
from flask import send_file
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import HRFlowable, Spacer


app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("WARNING: DATABASE_URL not found")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

print("VALUE:", repr(os.getenv("DATABASE_URL")))  # debug

engine = create_engine(
    DATABASE_URL,
    future=True,
    pool_pre_ping=True
)

# ---------------- DB INIT ----------------
def init_db():
    if not engine:
        print("No DB connection")
        return
        
    with engine.begin() as conn:

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            price DOUBLE PRECISION NOT NULL
        )
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS bills (
            id SERIAL PRIMARY KEY,
            customer_name TEXT NOT NULL,
            created_date TIMESTAMP DEFAULT NOW()
        )
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS bill_items (
            id SERIAL PRIMARY KEY,
            bill_id INTEGER REFERENCES bills(id) ON DELETE CASCADE,
            product_id INTEGER REFERENCES products(id),
            quantity DOUBLE PRECISION,
            unit_price DOUBLE PRECISION,
            discount DOUBLE PRECISION,
            final_price DOUBLE PRECISION,
            gst DOUBLE PRECISION DEFAULT 0,
            date_added TIMESTAMP DEFAULT NOW()
        )
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS payments (
            id SERIAL PRIMARY KEY,
            bill_id INTEGER REFERENCES bills(id) ON DELETE CASCADE,
            amount DOUBLE PRECISION,
            date TIMESTAMP DEFAULT NOW()
        )
        """))
        
    init_db()

# ---------------- ROUTES ----------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/billing")
def billing():
    return render_template("billing.html")

@app.route("/products")
def products():
    return render_template("products.html")

@app.route("/customers")
def customers():
    return render_template("customers.html")

# ---------- Product Routes ----------

@app.route("/add_product", methods=["POST"])
def add_product():
    data = request.json

    with engine.begin() as conn:
        result = conn.execute(text("""
            INSERT INTO products (name, price)
            VALUES (:name, :price)
            RETURNING id, name, price
        """), {
            "name": data["name"],
            "price": data["price"]
        })

        new_product = result.fetchone()  # returns (id, name, price)

    return jsonify({"success": True, "product": {
        "id": new_product.id,
        "name": new_product.name,
        "price": new_product.price
    }})

@app.route("/update_product/<int:id>", methods=["PUT"])
def update_product(id):
    data = request.get_json()
    name = data.get("name")
    price = data.get("price")

    if not name or price is None:
        return jsonify({"success": False, "error": "Invalid input"})

    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE products
            SET name=:name, price=:price
            WHERE id=:id
        """), {
            "name": name,
            "price": price,
            "id": id
        })

    return jsonify({"success": True})

@app.route("/get_products")
def get_products():
    q = request.args.get("q", "").strip()

    with engine.connect() as conn:
        if q:
            result = conn.execute(text("""
                SELECT * FROM products
                WHERE LOWER(name) LIKE LOWER(:q)
            """), {"q": f"%{q}%"})
        else:
            result = conn.execute(text("SELECT * FROM products"))

        rows = result.fetchall()

    data = [{"id": r.id, "name": r.name, "price": r.price} for r in rows]
    return jsonify(data)


@app.route("/search_product")
def search_product():
    q = request.args.get("q", "").strip()

    if not q:
        return jsonify([])

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT * FROM products
            WHERE LOWER(name) LIKE LOWER(:q)
        """), {"q": f"%{q}%"})

        rows = result.fetchall()

    data = [{"id": r.id, "name": r.name, "price": r.price} for r in rows]
    return jsonify(data)

@app.route("/products")
def products_page():
    q = request.args.get("q", "").strip()

    with engine.connect() as conn:
        if q:
            result = conn.execute(text("""
                SELECT * FROM products
                WHERE LOWER(name) LIKE LOWER(:q)
            """), {"q": f"%{q}%"})
        else:
            result = conn.execute(text("SELECT * FROM products"))

        rows = result.fetchall()

    products = [dict(r._mapping) for r in rows]
    return render_template("products.html", products=products, query=q)


@app.route("/delete_product/<int:id>", methods=["DELETE"])
def delete_product(id):
    with engine.begin() as conn:
        # Delete dependent bill items first
        conn.execute(
            text("DELETE FROM bill_items WHERE product_id = :id"),
            {"id": id}
        )

        # Then delete product
        conn.execute(
            text("DELETE FROM products WHERE id = :id"),
            {"id": id}
        )

    return jsonify({"success": True})

# ---------------- CUSTOMERS ----------------
@app.route("/get_customers")
def get_customers():
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, customer_name FROM bills
        """))

        rows = result.fetchall()

    data = [dict(r._mapping) for r in rows]
    return jsonify(data)

@app.route("/delete_customer/<int:id>", methods=["DELETE"])
def delete_customer(id):
    with engine.begin() as conn:
        conn.execute(text("""
            DELETE FROM bills WHERE id=:id
        """), {"id": id})

    return {"status": "deleted"}

@app.route("/search_bill")
def search_bill():
    name = request.args.get("name", "")

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, customer_name
            FROM bills
            WHERE customer_name LIKE :name
        """), {"name": f"%{name}%"})

        rows = result.fetchall()

    return jsonify([dict(r._mapping) for r in rows])

# ---------------- BILL ----------------
@app.route("/create_bill", methods=["POST"])
def create_bill():
    customer = request.json["customer"]

    with engine.begin() as conn:
        result = conn.execute(text("""
            INSERT INTO bills (customer_name, created_date)
            VALUES (:customer, NOW())
            RETURNING id
        """), {"customer": customer})

        bill_id = result.scalar()

    return {"bill_id": bill_id}

@app.route("/add_item", methods=["POST"])
def add_item():
    data = request.json

    with engine.begin() as conn:
        price = conn.execute(text("""
            SELECT price FROM products WHERE id=:id
        """), {"id": data["product_id"]}).scalar()

        qty = float(data["quantity"])
        disc = float(data["discount"])
        gst = float(data.get("gst", 0))

        base = price * qty
        final = base - (base * disc / 100)

        conn.execute(text("""
            INSERT INTO bill_items
            (bill_id, product_id, quantity, unit_price, discount, final_price, gst, date_added)
            VALUES (:bill_id, :product_id, :qty, :price, :disc, :final, :gst, NOW())
        """), {
            "bill_id": data["bill_id"],
            "product_id": data["product_id"],
            "qty": qty,
            "price": price,
            "disc": disc,
            "final": final,
            "gst": gst
        })

    return {"status": "ok"}

@app.route("/update_item/<int:id>", methods=["PUT"])
def update_item(id):
    data = request.json

    with engine.begin() as conn:
        price = conn.execute(text("""
            SELECT unit_price FROM bill_items WHERE id=:id
        """), {"id": id}).scalar()

        qty = float(data["quantity"])
        disc = float(data["discount"])
        gst = float(data.get("gst", 0))

        base = price * qty
        disc_amt = base * disc / 100

        # Final price (what customer sees)
        final = base - disc_amt

        # (optional calculations — same as your logic)
        gst_amount = final * gst / (100 + gst)
        base_without_gst = final - gst_amount

        conn.execute(text("""
            UPDATE bill_items
            SET quantity=:qty,
                discount=:disc,
                final_price=:final,
                gst=:gst
            WHERE id=:id
        """), {
            "qty": qty,
            "disc": disc,
            "final": final,
            "gst": gst,
            "id": id
        })

    return {"status": "updated"}

@app.route("/delete_item/<int:id>", methods=["DELETE"])
def delete_item(id):
    with engine.begin() as conn:
        conn.execute(text("""
            DELETE FROM bill_items WHERE id=:id
        """), {"id": id})

    return {"status": "deleted"}

@app.route("/get_bill/<int:bill_id>")
def get_bill(bill_id):

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT b.id, p.name, b.quantity, b.unit_price, b.discount,
                   b.final_price, b.gst, b.date_added
            FROM bill_items b
            JOIN products p ON b.product_id=p.id
            WHERE b.bill_id=:id
        """), {"id": bill_id})

        items = result.fetchall()

        subtotal = 0
        total_gst = 0

        for i in items:
            gst_amt = i.final_price * i.gst / (100 + i.gst)
            base = i.final_price - gst_amt

            subtotal += base
            total_gst += gst_amt

        total = subtotal + total_gst

        paid = conn.execute(text("""
            SELECT COALESCE(SUM(amount),0)
            FROM payments WHERE bill_id=:id
        """), {"id": bill_id}).scalar()

        balance = total - paid

    return jsonify({
        "items": [dict(i._mapping) for i in items],
        "subtotal": subtotal,
        "total_gst": total_gst,
        "total": total,
        "paid": paid,
        "balance": balance
    })

@app.route("/add_payment", methods=["POST"])
def add_payment():
    data = request.json

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO payments (bill_id, amount, date)
            VALUES (:bill_id, :amount, NOW())
        """), {
            "bill_id": data["bill_id"],
            "amount": data["amount"]
        })

    return {"status": "ok"}

@app.route("/download_bill/<int:bill_id>")
def download_bill(bill_id):
    gst_inclusive = request.args.get("gst_inclusive", "0") == "1"

    with engine.connect() as conn:

        # Get customer
        row = conn.execute(text("""
            SELECT customer_name FROM bills WHERE id=:id
        """), {"id": bill_id}).fetchone()

        if not row:
            return "Bill not found", 404

        customer = row.customer_name

        # Fetch items
        result = conn.execute(text("""
            SELECT p.name, b.quantity, b.unit_price, b.discount,
                   b.gst, b.final_price, b.date_added
            FROM bill_items b
            JOIN products p ON b.product_id = p.id
            WHERE b.bill_id=:id
        """), {"id": bill_id})

        items = result.fetchall()

        subtotal = 0
        total_gst = 0
        items_data = []

        for i in items:
            qty = i.quantity
            unit_price = i.unit_price
            discount = i.discount
            gst = i.gst

            base = qty * unit_price
            disc_amt = base * discount / 100
            final_price = base - disc_amt

            if gst_inclusive:
                gst_amt = final_price * gst / (100 + gst)
                base_price = final_price - gst_amt

                subtotal += base_price
                total_gst += gst_amt
                display_gst = None
            else:
                gst_amt = final_price * gst / 100
                subtotal += final_price
                total_gst += gst_amt
                display_gst = gst

            items_data.append({
                "date_added": str(i.date_added),
                "name": i.name,
                "quantity": qty,
                "unit_price": unit_price,
                "discount": discount,
                "gst": display_gst,
                "final_price": final_price
            })

        total = subtotal if gst_inclusive else subtotal + total_gst

        # Get payment
        paid = conn.execute(text("""
            SELECT COALESCE(SUM(amount),0)
            FROM payments WHERE bill_id=:id
        """), {"id": bill_id}).scalar()

        balance = total - paid

  # Create PDF
    pdf_folder = os.path.join(os.getcwd(), "bills")
    os.makedirs(pdf_folder, exist_ok=True)

    import time
    file_path = os.path.join(pdf_folder, f"{customer}_{bill_id}_{int(time.time())}.pdf")

    doc = SimpleDocTemplate(file_path, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

# Header
    logo_path = "static/logo.jpeg"
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=60, height=60)
    else:
        logo = Paragraph("LOGO MISSING", styles['Normal'])

    header_table = Table(
    [
        [
            logo,
            Paragraph(
                "<b>KHANRA TRADING</b><br/>Bhatora, Amta-II, Howrah<br/>+91 98362 41101<br/>GSTIN/UIN: 19AZFPK4346M1ZW <br/>",
                styles['Normal']
            )
        ]
    ],
    colWidths=[70, 400]
)
    header_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
    elements.append(header_table)
    elements.append(Spacer(1, 12))
    elements.append(HRFlowable(width="100%", thickness=1, lineCap='round', color=colors.black, spaceBefore=10, spaceAfter=10))
    elements.append(Spacer(1, 5))
    elements.append(Paragraph(f"Customer: {customer}", styles['Heading3']))
    elements.append(Spacer(1, 12))

# Table
    if gst_inclusive:
        table_data = [["Date", "Item", "Qty", "Amount"]]
        col_widths = [70, 180, 30, 100]
    else:
        table_data = [["Date", "Item", "Qty", "Amount"]]
        col_widths = [70, 180, 30, 100]

    for item in items_data:
    # Decide amount to display
        if gst_inclusive:
        # GST already included in final_price
            amount = f"Rs. {item['final_price']:.2f}"
        else:
            amount = f"Rs. {item['final_price']:.2f}"  # same as before, could also include GST separately if you want

        row = [
            item["date_added"].split()[0],
            item["name"],
            item["quantity"],
            amount
        ]
        table_data.append(row)

    col_widths = [80, 220, 60, 100]
    table = Table(table_data, hAlign='CENTER', colWidths=col_widths)
    table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))

# Totals
    if gst_inclusive:
        right_style = ParagraphStyle(name='right', parent=styles['Normal'], alignment=TA_RIGHT, fontName='Helvetica-Bold')
        elements.append(Paragraph(f"Subtotal: Rs. {subtotal:.2f}", right_style))
        elements.append(Paragraph(f"GST @18%: Rs. {total_gst:.2f}", right_style))
        elements.append(Paragraph(f"Total: Rs. {subtotal+total_gst:.2f}", right_style))
        elements.append(Spacer(1, 20))
    else:
        right_style = ParagraphStyle(name='right', parent=styles['Normal'], alignment=TA_RIGHT, fontName='Helvetica-Bold')
        elements.append(Paragraph(f"Subtotal: Rs. {subtotal:.2f}", right_style))
        elements.append(Paragraph(f"GST @18%: Rs. {total_gst:.2f}", right_style))
        elements.append(Paragraph(f"Total: Rs. {subtotal+total_gst:.2f}", right_style))
        elements.append(Spacer(1, 20))
    
    elements.append(HRFlowable(width="100%", thickness=1, lineCap='round', color=colors.black, spaceBefore=10, spaceAfter=10))
    elements.append(Spacer(1, 5))
     
    bank_style = ParagraphStyle(
        name='bank',
        parent=styles['Normal'],
        alignment=TA_LEFT,
        fontSize=10,
        leading=12
    )
    bank_details = """
    <b>Bank Account Details:</b><br/>
    <b>Bank:</b> STATE BANK OF INDIA<br/>
    <b>Branch:</b> Bakshi Branch<br/>
    <b>Branch Code:</b> 14087<br/>
    <b>A/C Name:</b> KHANRA TRADING<br/>
    <b>IFSC:</b> SBIN0014087<br/>
    <b>MICR:</b> 700002611<br/>
    <b>A/C No.:</b> 42184423014<br/>
    <b>Mobile:</b> 9836241101
    """
    elements.append(Paragraph(bank_details, bank_style))
    elements.append(Spacer(1, 20))
    right_style = ParagraphStyle(name='right', parent=styles['Normal'], alignment=TA_RIGHT, fontName='Helvetica-Bold')
    elements.append(Paragraph("Customer's Signature: _______________________", right_style))

    elements.append(HRFlowable(width="100%", thickness=1, lineCap='round', color=colors.black, spaceBefore=10, spaceAfter=10))
    elements.append(Spacer(1, 5))

    footer_style = ParagraphStyle(
    name='footer',
    parent=styles['Normal'],
    alignment=TA_CENTER,
    fontSize=11,
    leading=14,
    fontName='Helvetica-Bold'
    )
    elements.append(Paragraph("Thank you for shopping with us!", footer_style))

    doc.build(elements)

    return send_file(
        file_path,
        as_attachment=True,
        download_name=f"{customer}_{bill_id}.pdf",
        mimetype='application/pdf'
    )

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/api/sales_overview")
def sales_overview():
    with engine.begin() as conn:

        today = conn.execute(text("""
            SELECT COALESCE(SUM(final_price),0)
            FROM bill_items
            WHERE DATE(date_added) = CURRENT_DATE
        """)).scalar()

        month = conn.execute(text("""
            SELECT COALESCE(SUM(final_price),0)
            FROM bill_items
            WHERE EXTRACT(MONTH FROM date_added) = EXTRACT(MONTH FROM CURRENT_DATE)
            AND EXTRACT(YEAR FROM date_added) = EXTRACT(YEAR FROM CURRENT_DATE)
        """)).scalar()

        year = conn.execute(text("""
            SELECT COALESCE(SUM(final_price),0)
            FROM bill_items
            WHERE EXTRACT(YEAR FROM date_added) = EXTRACT(YEAR FROM CURRENT_DATE)
        """)).scalar()

    return jsonify({
        "today": float(today or 0),
        "month": float(month or 0),
        "year": float(year or 0)
    })

@app.route("/api/credit_total")
def credit_total():
    with engine.begin() as conn:

        total_billed = conn.execute(text("""
            SELECT COALESCE(SUM(final_price),0) FROM bill_items
        """)).scalar()

        total_paid = conn.execute(text("""
            SELECT COALESCE(SUM(amount),0) FROM payments
        """)).scalar()

    return jsonify({
        "pending": float(total_billed - total_paid)
    })

@app.route("/api/month_comparison")
def month_comparison():
    with engine.connect() as conn:

        this_month = conn.execute(text("""
            SELECT COALESCE(SUM(final_price),0)
            FROM bill_items
            WHERE DATE_TRUNC('month', date_added) = DATE_TRUNC('month', CURRENT_DATE)
        """)).scalar()

        last_month = conn.execute(text("""
            SELECT COALESCE(SUM(final_price),0)
            FROM bill_items
            WHERE DATE_TRUNC('month', date_added) = DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
        """)).scalar()

    growth = 0
    if last_month > 0:
        growth = ((this_month - last_month) / last_month) * 100

    return jsonify({
        "this_month": float(this_month),
        "last_month": float(last_month),
        "growth": round(growth, 2)
    })

@app.route("/api/top_products")
def top_products():
    with engine.begin() as conn:

        rows = conn.execute(text("""
            SELECT COALESCE(p.name, 'Deleted Product') AS name,
                   COALESCE(SUM(bi.quantity), 0) AS qty
            FROM bill_items bi
            LEFT JOIN products p ON p.id = bi.product_id
            GROUP BY p.name
            ORDER BY qty DESC
            LIMIT 10
        """)).mappings().all()

    return jsonify([dict(r) for r in rows])

@app.route("/api/customer_insights")
def customer_insights():
    with engine.begin() as conn:

        total_customers = conn.execute(text("""
            SELECT COUNT(DISTINCT customer_name) FROM bills
        """)).scalar() or 0

        rows = conn.execute(text("""
            SELECT b.customer_name,
                   COALESCE(SUM(bi.final_price),0) as total
            FROM bills b
            LEFT JOIN bill_items bi ON b.id = bi.bill_id
            GROUP BY b.customer_name
            ORDER BY total DESC
            LIMIT 5
        """)).mappings().all()

    return jsonify({
        "total_customers": int(total_customers),
        "top_customers": [dict(r) for r in rows]
    })
# ---------------- MAIN ----------------
if __name__ == "__main__":
    app.run(debug=True)
