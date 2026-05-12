import threading
from flask import Flask, render_template, request, jsonify
import webview
import models
from sqlmodel import create_engine, SQLModel, Session, select, update, delete
from reportlab.lib.pagesizes import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.units import mm as mm_unit
from datetime import datetime
from sqlalchemy import text, inspect
import os
import socket

app = Flask(__name__)
sqlite_url = "sqlite:///database.db"
engine = create_engine(sqlite_url, pool_pre_ping=True)


def sync_database_schema():
    # Create tables if they don't exist (handles new tables)
    SQLModel.metadata.create_all(engine)
    
    # Get all model definitions
    from models import Product, Category, Supplier, Cashbox, Sale
    
    models_map = {
        'product': Product,
        'category': Category,
        'supplier': Supplier,
        'cashbox': Cashbox,
        'sale': Sale,
    }
    
    with engine.connect() as conn:
        inspector = inspect(engine)
        
        for table_name, model_class in models_map.items():
            if not inspector.has_table(table_name):
                continue
                
            # Get existing columns
            existing_columns = [col['name'] for col in inspector.get_columns(table_name)]
            
            # Get model columns (from SQLModel/SQLAlchemy)
            model_columns = {}
            for column in model_class.__table__.columns:
                model_columns[column.name] = {
                    'type': str(column.type),
                    'nullable': column.nullable,
                    'default': column.default
                }
            
            # Add missing columns
            for col_name, col_info in model_columns.items():
                if col_name not in existing_columns:
                    # Determine SQLite type
                    if 'INT' in col_info['type'].upper():
                        sql_type = 'INTEGER'
                    elif 'FLOAT' in col_info['type'].upper() or 'DECIMAL' in col_info['type'].upper():
                        sql_type = 'FLOAT'
                    elif 'BOOL' in col_info['type'].upper():
                        sql_type = 'BOOLEAN'
                    elif 'DATETIME' in col_info['type'].upper() or 'TIMESTAMP' in col_info['type'].upper():
                        sql_type = 'TIMESTAMP'
                    else:
                        sql_type = 'VARCHAR(500)'
                    
                    try:
                        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {sql_type}"))
                        conn.commit()
                        print(f"  ✅ Added column '{col_name}' to '{table_name}' table")
                    except Exception as e:
                        print(f"  ⚠️ Could not add column '{col_name}': {e}")

sync_database_schema()

# Printer Settings
PAGE_WIDTH  = 80 * mm_unit
PAGE_HEIGHT = 200 * mm_unit
MARGIN      = 4 * mm_unit
STORE_INFO = {
    "name":    "متجر",
    "address": "عنوان المتجر",
    "phone":   "رقم الهاتف",
}
 
BILL_INFO = {
    "bill_no":   "0000",
    "date":      datetime.now().strftime("%Y-%m-%d %H:%M"),
    "cashier":   "اسم البائع",
    "customer":  "Walk-in Customer",
}
CURRENCY   = "DA"


# Printer functions
def make_styles():
    return {
        "title": ParagraphStyle("title",
            fontName="Helvetica-Bold", fontSize=11,
            alignment=TA_CENTER, spaceAfter=1),
 
        "center": ParagraphStyle("center",
            fontName="Helvetica", fontSize=7,
            alignment=TA_CENTER, spaceAfter=1),
 
        "left": ParagraphStyle("left",
            fontName="Helvetica", fontSize=7,
            alignment=TA_LEFT, spaceAfter=1),
 
        "right": ParagraphStyle("right",
            fontName="Helvetica", fontSize=7,
            alignment=TA_RIGHT, spaceAfter=1),
 
        "bold_left": ParagraphStyle("bold_left",
            fontName="Helvetica-Bold", fontSize=7,
            alignment=TA_LEFT, spaceAfter=1),
 
        "bold_right": ParagraphStyle("bold_right",
            fontName="Helvetica-Bold", fontSize=8,
            alignment=TA_RIGHT, spaceAfter=1),
 
        "total": ParagraphStyle("total",
            fontName="Helvetica-Bold", fontSize=9,
            alignment=TA_RIGHT, spaceAfter=1),
 
        "footer": ParagraphStyle("footer",
            fontName="Helvetica-Oblique", fontSize=6,
            alignment=TA_CENTER, spaceAfter=1),
    }

def build_bill(cart_items, output_path=f"bills/bill.pdf"):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=(PAGE_WIDTH, PAGE_HEIGHT),
        rightMargin=MARGIN,
        leftMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
    )
 
    s = make_styles()
    col_w = PAGE_WIDTH - 2 * MARGIN   # usable width
    story = []
 
    # ── Header ──────────────────────────────
    story.append(Paragraph(STORE_INFO["name"], s["title"]))
    story.append(Paragraph(STORE_INFO["address"], s["center"]))
    story.append(Paragraph(STORE_INFO["phone"], s["center"]))
    story.append(Spacer(1, 2 * mm_unit))
    story.append(HRFlowable(width=col_w, thickness=0.5, color=colors.black))
    story.append(Spacer(1, 1 * mm_unit))
 
    # ── Bill Info ───────────────────────────
    info_data = [
        [Paragraph(f"Bill #: {BILL_INFO['bill_no']}", s["left"]),
         Paragraph(f"Date: {BILL_INFO['date']}", s["right"])],
        [Paragraph(f"Cashier: {BILL_INFO['cashier']}", s["left"]),
         Paragraph(f"Customer: {BILL_INFO['customer']}", s["right"])],
    ]
    info_table = Table(info_data, colWidths=[col_w * 0.55, col_w * 0.45])
    info_table.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP")]))
    story.append(info_table)
    story.append(Spacer(1, 1 * mm_unit))
    story.append(HRFlowable(width=col_w, thickness=0.5, color=colors.black, dash=(2,2)))
    story.append(Spacer(1, 1 * mm_unit))
 
    # ── Items Header ────────────────────────
    hdr = [
        Paragraph("<b>Item</b>", s["bold_left"]),
        Paragraph("<b>Qty</b>", s["bold_right"]),
        Paragraph("<b>Price</b>", s["bold_right"]),
        Paragraph("<b>Total</b>", s["bold_right"]),
    ]
    # Column widths: description takes most space
    cw = [col_w * 0.42, col_w * 0.12, col_w * 0.22, col_w * 0.24]
 
    rows = [hdr]
    subtotal = 0.0
 
    for desc, qty, price in cart_items:
        line_total = qty * price
        subtotal  += line_total
        rows.append([
            Paragraph(desc, s["left"]),
            Paragraph(str(qty), s["right"]),
            Paragraph(f"{price:.2f}", s["right"]),
            Paragraph(f"{line_total:.2f}", s["right"]),
        ])
 
    items_table = Table(rows, colWidths=cw)
    items_table.setStyle(TableStyle([
        ("VALIGN",      (0,0), (-1,-1), "TOP"),
        ("LINEBELOW",   (0,0), (-1,0),  0.5, colors.black),
        ("LINEABOVE",   (0,1), (-1,1),  0.25, colors.lightgrey),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F5F5F5")]),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 1 * mm_unit))
    story.append(HRFlowable(width=col_w, thickness=0.5, color=colors.black, dash=(2,2)))
    story.append(Spacer(1, 1 * mm_unit))
 
    # ── Totals ──────────────────────────────
    grand_total  = subtotal
 
    totals_data = [
        [Paragraph("Subtotal:", s["bold_left"]),
         Paragraph(f"{subtotal:.2f} {CURRENCY}", s["right"])],
    ]
    totals_data.append([
        Paragraph("<b>TOTAL:</b>", s["total"]),
        Paragraph(f"<b>{grand_total:.2f} {CURRENCY}</b>", s["total"]),
    ])
 
    totals_table = Table(totals_data, colWidths=[col_w * 0.55, col_w * 0.45])
    totals_table.setStyle(TableStyle([
        ("VALIGN",    (0,0), (-1,-1), "TOP"),
        ("LINEABOVE", (0,-1), (-1,-1), 0.8, colors.black),
    ]))
    story.append(totals_table)
 
    story.append(Spacer(1, 3 * mm_unit))
    story.append(HRFlowable(width=col_w, thickness=0.5, color=colors.black))
    story.append(Spacer(1, 2 * mm_unit))
 
    # ── Footer ──────────────────────────────
    story.append(Paragraph("شراء لشرائكم من عندنا", s["footer"]))
    story.append(Spacer(1, 4 * mm_unit))  # Feed space for paper cut
 
    # ── Build ───────────────────────────────
    doc.build(story)
    print(f"Bill saved to: {os.path.abspath(output_path)}")
    return output_path

# Create tables
SQLModel.metadata.create_all(engine)

@app.route('/')
def home():
    return render_template('index.html')

# ==================== PRODUCTS API ====================
@app.route('/api/products', methods=['GET'])
def get_products():
    with Session(engine) as session:
        products = session.exec(select(models.Product)).all()
        return jsonify([{
            'id': p.id,
            'title': p.title,
            'barcode': p.barcode,
            'category': p.category_id,
            'quantity': p.quantity,
            'price': p.price,
            'exp': p.exp if hasattr(p, 'exp') else None
        } for p in products])

@app.route('/api/products', methods=['POST'])
def add_product():
    data = request.json
    with Session(engine) as session:
        new_product = models.Product(
            title=data['title'],
            barcode=data['barcode'],
            category_id=data.get('category_id'),
            supplier_id=data.get('supplier_id'),
            quantity=data['quantity'],
            price=data['price'],
            item_per_box=data.get('item_per_box'),
            box_price=data.get('box_price'),
            cashbox_id=data.get('cashbox_id')
        )
        session.add(new_product)
        session.commit()
        session.refresh(new_product)
        return jsonify({'success': True, 'id': new_product.id})

@app.route('/api/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    data = request.json
    with Session(engine) as session:
        stmt = update(models.Product).where(models.Product.id == product_id).values(**data)
        session.exec(stmt)
        session.commit()
        return jsonify({'success': True})

@app.route('/api/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    with Session(engine) as session:
        stmt = delete(models.Product).where(models.Product.id == product_id)
        session.exec(stmt)
        session.commit()
        return jsonify({'success': True})

# ==================== CATEGORIES API ====================
@app.route('/api/categories', methods=['GET'])
def get_categories():
    with Session(engine) as session:
        categories = session.exec(select(models.Category)).all()
        return jsonify([{'id': c.id, 'title': c.title} for c in categories])

@app.route('/api/categories', methods=['POST'])
def add_category():
    data = request.json
    with Session(engine) as session:
        new_category = models.Category(title=data['title'])
        session.add(new_category)
        session.commit()
        session.refresh(new_category)
        return jsonify({'success': True, 'id': new_category.id})

# ==================== SUPPLIERS API ====================
@app.route('/api/suppliers', methods=['GET'])
def get_suppliers():
    with Session(engine) as session:
        suppliers = session.exec(select(models.Supplier)).all()
        return jsonify([{
            'id': s.id,
            'name': s.name,
            'phone': s.phone,
            'email': s.email
        } for s in suppliers])

@app.route('/api/suppliers', methods=['POST'])
def add_supplier():
    data = request.json
    with Session(engine) as session:
        new_supplier = models.Supplier(
            name=data['name'],
            phone=data['phone'],
            email=data['email']
        )
        session.add(new_supplier)
        session.commit()
        session.refresh(new_supplier)
        return jsonify({'success': True, 'id': new_supplier.id})

@app.route('/api/suppliers/<int:supplier_id>', methods=['DELETE'])
def delete_supplier(supplier_id):
    with Session(engine) as session:
        stmt = delete(models.Supplier).where(models.Supplier.id == supplier_id)
        session.exec(stmt)
        session.commit()
        return jsonify({'success': True})

# ==================== CASHBOX API ====================
@app.route('/api/cashboxes', methods=['GET'])
def get_cashboxes():
    with Session(engine) as session:
        cashboxes = session.exec(select(models.Cashbox)).all()
        return jsonify([{
            'id': c.id,
            'title': c.title,
            'drawer': c.drawer
        } for c in cashboxes])

@app.route('/api/cashboxes', methods=['POST'])
def add_cashbox():
    data = request.json
    with Session(engine) as session:
        new_cashbox = models.Cashbox(
            title=data['title'],
            drawer=data['drawer']
        )
        session.add(new_cashbox)
        session.commit()
        session.refresh(new_cashbox)
        return jsonify({'success': True, 'id': new_cashbox.id})

@app.route('/api/cashboxes/<int:cashbox_id>', methods=['PUT'])
def update_cashbox(cashbox_id):
    data = request.json
    with Session(engine) as session:
        stmt = update(models.Cashbox).where(models.Cashbox.id == cashbox_id).values(drawer=data['drawer'])
        session.exec(stmt)
        session.commit()
        return jsonify({'success': True})
# ==================== CUSTOMERS API ================
@app.route('/api/customers/', methods=["GET"])
def get_customers():
    with Session(engine) as session:
        customers = session.exec(select(models.Customer)).all()
        return jsonify([{
            'id': c.id,
            'name': c.name,
            'phone': c.phone,
            'debt': c.debt
        } for c in customers])
    
@app.route('/api/customers/add', methods=['POST'])
def add_customer():
    data = request.json
    with Session(engine) as session:
        new_customer = models.Customer(
            name=data['name'],
            phone=data['phone'],
            debt=data['debt']
        )
        session.add(new_customer)
        session.commit()
        session.refresh(new_customer)
        return jsonify({'success': True, 'id': new_customer.id})
    
@app.route('/api/customers/delete/<int:customer_id>', methods=['DELETE'])
def delete_customer(customer_id):
    with Session(engine) as session:
        stmt = delete(models.Customer).where(models.Customer.id == customer_id)
        session.exec(stmt)
        session.commit()
        return jsonify({'success': True})

# ==================== SALES API ====================
@app.route('/api/sales', methods=['GET'])
def get_sales():
    with Session(engine) as session:
        sales = session.exec(select(models.Sale).order_by(models.Sale.date.desc())).all()
        result = []
        for sale in sales:
            product = session.get(models.Product, sale.product_id) if sale.product_id else None
            result.append({
                'id': sale.id,
                'product_id': sale.product_id,
                'product_title': product.title if product else None,
                'product_barcode': product.barcode if product else None,
                'price': product.price if product else 0,
                'quantity': sale.quantity,
                'total': sale.total,
                'date': sale.date.isoformat()
            })
        return jsonify(result)
    
@app.route('/api/sales/add', methods=['POST'])
def add_sale():
    data = request.json
    with Session(engine) as session:
        # Create sale record
        new_sale = models.Sale(
            product_id=data['product_id'],
            quantity=data['quantity'],
            total=data['total']
        )
        session.add(new_sale)
        
        # Update product stock
        product = session.get(models.Product, data['product_id'])
        if product:
            product.quantity -= data['quantity']
        
        # Update Drawer
        cashbox = session.get(models.Cashbox, product.cashbox_id)
        if cashbox:
            cashbox.drawer += data['total']
        
        session.commit()
        return jsonify({'success': True})

@app.route('/api/sales/stats', methods=['GET'])
def get_sales_stats():
    with Session(engine) as session:
        sales = session.exec(select(models.Sale)).all()
        total_sales = sum(s.quantity * s.product.price if s.product else 0 for s in sales)
        return jsonify({
            'total_sales': total_sales,
            'transaction_count': len(sales)
        })

@app.route('/api/print', methods=['POST'])
def print_bill():
    data = request.json
    for item in data['products']:
        with Session(engine) as session:
            # Create sale record
            new_sale = models.Sale(
                item=data['product_id'],
                quantity=data['quantity'],
            )
            session.add(new_sale)
            
            # Update product stock
            product = session.get(models.Product, data['product_id'])
            if product:
                product.quantity -= data['quantity']
            
            session.commit()
    bill_path = build_bill(data['products'])
    return jsonify({'success': True})

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

port = find_free_port()

def start_flask():
    app.run(port=port, debug=False)

if __name__ == '__main__':
    # Initialize sample data if database is empty
    with Session(engine) as session:
        # Check if categories exist
        categories = session.exec(select(models.Category)).all()
        if not categories:
            sample_categories = [
                models.Category(title='Electronics'),
                models.Category(title='Books'),
                models.Category(title='Services'),
                models.Category(title='School')
            ]
            for cat in sample_categories:
                session.add(cat)
            session.commit()
        
        # Check if products exist
        products = session.exec(select(models.Product)).all()
        if not products:
            sample_products = [
                models.Product(title='Laptop', barcode='615001', category_id=1, quantity=50, price=45000),
                models.Product(title='Mouse', barcode='615002', category_id=1, quantity=200, price=1500),
                models.Product(title='Python Book', barcode='615003', category_id=2, quantity=100, price=2500),
                models.Product(title='Consulting', barcode='615004', category_id=3, quantity=999, price=5000),
                models.Product(title='Notebook', barcode='615005', category_id=4, quantity=500, price=200)
            ]
            for prod in sample_products:
                session.add(prod)
            session.commit()
    
    t = threading.Thread(target=start_flask)
    t.daemon = True
    t.start()

    webview.create_window('Cashbox Pro', f'http://127.0.0.1:{port}', width=1400, height=800, text_select=True)
    webview.start()