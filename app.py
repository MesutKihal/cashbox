import customtkinter as ctk
import threading
from flask import Flask, render_template, request, jsonify
import webview
import models
from sqlmodel import create_engine, SQLModel, Session, select, update, delete
import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.pagesizes import mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.units import mm as mm_unit
from datetime import datetime
from reportlab.pdfbase.ttfonts import TTFont
from sqlalchemy import text, inspect
import os
import socket

# Set the overall appearance and color theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class LoginForm(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configure window settings
        self.title("Cashbox")
        self.geometry("600x600")
        self.resizable(False, False)

        # Center the window on the screen
        self.eval('tk::PlaceWindow . center')

        # Create a central background frame (The "Login Card")
        self.card_frame = ctk.CTkFrame(master=self, width=800, height=420, corner_radius=15)
        self.card_frame.place(relx=0.5, rely=0.5, anchor="center")

        # --- App Branding / Logo ---
        self.logo_label = ctk.CTkLabel(
            master=self.card_frame, 
            text="", 
            font=ctk.CTkFont(size=40)
        )
        self.logo_label.pack(pady=(35, 5))

        self.title_label = ctk.CTkLabel(
            master=self.card_frame, 
            text="Login", 
            font=ctk.CTkFont(family="Helvetica", size=24, weight="bold")
        )
        self.title_label.pack(pady=(0, 5))

        self.subtitle_label = ctk.CTkLabel(
            master=self.card_frame, 
            text="Please sign in to continue", 
            font=ctk.CTkFont(family="Helvetica", size=12),
            text_color="gray"
        )
        self.subtitle_label.pack(pady=(0, 25))

        # --- Input Fields ---
        # Username
        self.username_entry = ctk.CTkEntry(
            master=self.card_frame, 
            width=280, 
            height=45,
            placeholder_text="Username",
            border_width=1,
            corner_radius=8
        )
        self.username_entry.pack(pady=10)

        # Password entry
        self.password_entry = ctk.CTkEntry(
            master=self.card_frame, 
            width=280, 
            height=45,
            placeholder_text="Password",
            show="*",
            border_width=1,
            corner_radius=8
        )
        self.password_entry.pack(pady=10)


        # --- Submit Button ---
        self.login_button = ctk.CTkButton(
            master=self.card_frame, 
            text="Sign In", 
            width=280, 
            height=45,
            corner_radius=8,
            font=ctk.CTkFont(family="Helvetica", size=15, weight="bold"),
            command=self.handle_login
        )
        self.login_button.pack(pady=(10, 15))


    def handle_login(self):
        username = self.username_entry.get()
        password = self.password_entry.get()
        
        # Simple validation feedback
        if not username or not password:
            print("Error: Please fill in all fields.")
            return
        elif username == 'admin' and password == 'admin':
            self.destroy()
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
            

app = Flask(__name__)
sqlite_url = "sqlite:///database.db"
engine = create_engine(sqlite_url, pool_pre_ping=True)


def sync_database_schema():
    SQLModel.metadata.create_all(engine)
    
    from models import Product, Category, Supplier, Cashbox, Sale, Settings, Bill
    
    models_map = {
        'product': Product,
        'category': Category,
        'supplier': Supplier,
        'cashbox': Cashbox,
        'sale': Sale,
        'settings': Settings,
        'bill': Bill,
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
PAGE_HEIGHT = 80 * mm_unit
MARGIN      = 4 * mm_unit

STORE_INFO = {
    "name": "CashboxPro",
    "address": "330 logts",
    "phone": "05 55 55 55 55",
    "rc": "21 123 4567 1234567",         
    "nif": "123456789012345",        
    "nis": "123456789012345",            
    "art_imp": "22",                      
    "tax_id": "123456789"                
}

with Session(engine) as session:
    settings = session.exec(select(models.Settings)).first()
    STORE_INFO = {
            'name': settings.store_name,
            'phone': settings.store_phone,
            'address': settings.store_address,
            'rc': settings.rc,
            'nif': settings.nif,
            'nis': settings.nis,
            'art_imp': settings.art_imp,
            'tax_id': "123456789",
    }

 
BILL_INFO = {
    "bill_no":   "0000",
    "date":      datetime.now().strftime("%Y-%m-%d %H:%M"),
    "cashier":   "اسم البائع",
}
CURRENCY   = "DA"


FONT_PATH = "static/assets/font/NotoSansArabic-Regular.ttf"
if os.path.exists(FONT_PATH):
    pdfmetrics.registerFont(TTFont('ArabicFont', FONT_PATH))
    DEFAULT_FONT = 'ArabicFont'
else:
    DEFAULT_FONT = 'Helvetica'  # fallback – will not show Arabic correctly

def reshape_arabic(text):
    """Reshape and reorder Arabic text for ReportLab"""
    if not text:
        return ""
    reshaped = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped)
    return bidi_text

def make_styles():
    """Create paragraph styles with Arabic font support"""
    styles = getSampleStyleSheet()
    
    # Override default styles with Arabic font
    style_map = {
        "title": ParagraphStyle(
            "title",
            parent=styles["Title"],
            fontName=DEFAULT_FONT,
            fontSize=11,
            alignment=TA_CENTER,
            spaceAfter=1,
        ),
        "center": ParagraphStyle(
            "center",
            parent=styles["Normal"],
            fontName=DEFAULT_FONT,
            fontSize=7,
            alignment=TA_CENTER,
            spaceAfter=1,
        ),
        "left": ParagraphStyle(
            "left",
            parent=styles["Normal"],
            fontName=DEFAULT_FONT,
            fontSize=7,
            alignment=TA_LEFT,
            spaceAfter=1,
        ),
        "right": ParagraphStyle(
            "right",
            parent=styles["Normal"],
            fontName=DEFAULT_FONT,
            fontSize=7,
            alignment=TA_RIGHT,
            spaceAfter=1,
        ),
        "bold_left": ParagraphStyle(
            "bold_left",
            parent=styles["Normal"],
            fontName=DEFAULT_FONT,
            fontSize=7,
            alignment=TA_LEFT,
            spaceAfter=1,
        ),
        "bold_right": ParagraphStyle(
            "bold_right",
            parent=styles["Normal"],
            fontName=DEFAULT_FONT,
            fontSize=8,
            alignment=TA_RIGHT,
            spaceAfter=1,
        ),
        "bold_center": ParagraphStyle(
            "bold_center",
            parent=styles["Normal"],
            fontName=DEFAULT_FONT,
            fontSize=8,
            alignment=TA_CENTER,
            spaceAfter=1,
        ),
        "total": ParagraphStyle(
            "total",
            parent=styles["Normal"],
            fontName=DEFAULT_FONT,
            fontSize=9,
            alignment=TA_RIGHT,
            spaceAfter=1,
        ),
        "footer": ParagraphStyle(
            "footer",
            parent=styles["Normal"],
            fontName=DEFAULT_FONT,
            fontSize=6,
            alignment=TA_CENTER,
            spaceAfter=1,
        ),
    }
    return style_map

billCount = 0
with Session(engine) as session:
    billCount = len(session.exec(select(models.Bill)).all())

def build_bill(cart_items, customer_id, output_path=f"bills/bill{billCount + 1}.pdf"):
    PAGE_HEIGHT = (len(cart_items) * 10 + 100) * mm_unit
    doc = SimpleDocTemplate(
        output_path,
        pagesize=(PAGE_WIDTH, PAGE_HEIGHT),
        rightMargin=MARGIN,
        leftMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
    )

    s = make_styles()
    col_w = PAGE_WIDTH - 2 * MARGIN
    story = []
 
    # Header – all Arabic text must be reshaped
    story.append(Paragraph(reshape_arabic(STORE_INFO["name"]), s["title"]))
    story.append(Paragraph(reshape_arabic(STORE_INFO["address"]), s["center"]))
    story.append(Paragraph(reshape_arabic(STORE_INFO["phone"]), s["center"]))
    story.append(Spacer(1, 2 * mm_unit))
    story.append(HRFlowable(width=col_w, thickness=0.5, color=colors.black))
    story.append(Spacer(1, 1 * mm_unit))
 
    # Bill Info
    with Session(engine) as session:
        customer = session.get(models.Customer, customer_id)
        customer = customer.name if customer else "..."
        info_data = [
            [Paragraph(reshape_arabic(f"رقم الفاتورة: {BILL_INFO['bill_no']}"), s["left"]),
            Paragraph(reshape_arabic(f"التاريخ: {BILL_INFO['date']}"), s["right"])],
            [Paragraph(reshape_arabic(f"أمين الصندوق: {BILL_INFO['cashier']}"), s["left"]),
            Paragraph(reshape_arabic(f"الزبون: {customer}"), s["right"])],
        ]
    info_table = Table(info_data, colWidths=[col_w * 0.55, col_w * 0.45])
    info_table.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP")]))
    story.append(info_table)
    story.append(Spacer(1, 1 * mm_unit))
    story.append(HRFlowable(width=col_w, thickness=0.5, color=colors.black, dash=(2,2)))
    story.append(Spacer(1, 1 * mm_unit))
 
    # Items Header
    hdr = [
        Paragraph(reshape_arabic("<b>المنتج</b>"), s["bold_left"]),
        Paragraph(reshape_arabic("<b>الكمية</b>"), s["bold_right"]),
        Paragraph(reshape_arabic("<b>السعر</b>"), s["bold_right"]),
        Paragraph(reshape_arabic("<b>الإجمالي</b>"), s["bold_right"]),
    ]
    cw = [col_w * 0.42, col_w * 0.12, col_w * 0.22, col_w * 0.24]
 
    rows = [hdr]
    subtotal = 0.0

    for item in cart_items:
        line_total = item['quantity'] * item['price']
        subtotal += line_total
        rows.append([
            Paragraph(reshape_arabic(item['title']), s["left"]),
            Paragraph(str(item['quantity']), s["right"]),
            Paragraph(f"{item['price']:.2f}", s["right"]),
            Paragraph(f"{line_total:.2f}", s["right"]),
        ])
 
    items_table = Table(rows, colWidths=cw)
    items_table.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LINEBELOW", (0,0), (-1,0), 0.5, colors.black),
        ("LINEABOVE", (0,1), (-1,1), 0.25, colors.lightgrey),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F5F5F5")]),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 1 * mm_unit))
    story.append(HRFlowable(width=col_w, thickness=0.5, color=colors.black, dash=(2,2)))
    story.append(Spacer(1, 1 * mm_unit))
 
    # Totals
    grand_total = subtotal
 
    totals_data = [
        [Paragraph(reshape_arabic("المجموع الفرعي:"), s["bold_left"]),
         Paragraph(f"{subtotal:.2f} {CURRENCY}", s["right"])],
        [Paragraph(reshape_arabic("<b>الإجمالي:</b>"), s["total"]),
         Paragraph(f"<b>{grand_total:.2f} {CURRENCY}</b>", s["total"])],
    ]
 
    totals_table = Table(totals_data, colWidths=[col_w * 0.55, col_w * 0.45])
    totals_table.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LINEABOVE", (0,-1), (-1,-1), 0.8, colors.black),
    ]))
    story.append(totals_table)
 
    story.append(Spacer(1, 3 * mm_unit))
    story.append(HRFlowable(width=col_w, thickness=0.5, color=colors.black))
    story.append(Spacer(1, 2 * mm_unit))
 
    # Footer
    story.append(Paragraph(reshape_arabic("شكراً لتسوقكم معنا"), s["footer"]))
    story.append(Spacer(1, 4 * mm_unit))
 
    doc.build(story)
    with Session(engine) as session:
        new_bill = models.Bill(
                file_name = output_path,
                type="bon",
            )
        session.add(new_bill)
        session.commit()
    print(f"Bill saved to: {os.path.abspath(output_path)}")
    return output_path


def build_proforma_pdf(cart_items, customer_info, output_path=f"bills/proforma{billCount + 1}.pdf", invoice_number="1"):

    if output_path is None:
        global BILL_COUNTER
        BILL_COUNTER += 1
        output_path = f"bills/proforma_{datetime.now().strftime('%Y%m%d')}_{BILL_COUNTER:04d}.pdf"
    
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=15*mm,
        leftMargin=15*mm,
        topMargin=15*mm,
        bottomMargin=15*mm,
    )
    
    # Create bold styles (French only, no Arabic reshaping needed)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    styles = getSampleStyleSheet()
    
    bold_title = ParagraphStyle(
        'bold_title', parent=styles['Title'],
        fontName='Helvetica-Bold', fontSize=16, alignment=TA_CENTER, spaceAfter=6,
        textColor=colors.HexColor('#1a3e60')
    )
    bold_center = ParagraphStyle(
        'bold_center', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=10, alignment=TA_CENTER, spaceAfter=3
    )
    bold_left = ParagraphStyle(
        'bold_left', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=10, alignment=TA_LEFT, spaceAfter=3
    )
    normal_center = ParagraphStyle(
        'normal_center', parent=styles['Normal'],
        fontName='Helvetica', fontSize=9, alignment=TA_CENTER, spaceAfter=3
    )
    normal_left = ParagraphStyle(
        'normal_left', parent=styles['Normal'],
        fontName='Helvetica', fontSize=9, alignment=TA_LEFT, spaceAfter=3
    )
    table_header = ParagraphStyle(
        'table_header', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=10, alignment=TA_CENTER, textColor=colors.white
    )
    table_cell = ParagraphStyle(
        'table_cell', parent=styles['Normal'],
        fontName='Helvetica', fontSize=9, alignment=TA_RIGHT
    )
    table_cell_left = ParagraphStyle(
        'table_cell_left', parent=styles['Normal'],
        fontName='Helvetica', fontSize=9, alignment=TA_LEFT
    )
    
    story = []
    
    # ----- Header (French) -----
    # Company name (bold, large)
    story.append(Paragraph(STORE_INFO["name"].upper(), bold_title))
    story.append(Paragraph(STORE_INFO["address"], normal_center))
    story.append(Paragraph(f"Tel : {STORE_INFO['phone']}", normal_center))
    story.append(Spacer(1, 2*mm))
    
    # Tax information (French labels)
    tax_info = [
        f"RC (Registre de commerce) : {STORE_INFO.get('rc', '00 000 0000 0000000')}",
        f"NIF (Identifiant fiscal) : {STORE_INFO.get('nif', '000000000000000')}",
        f"NIS (Numéro d'identification sociale) : {STORE_INFO.get('nis', '000000000000000')}",
        f"ART IMP (Article d'imposition) : {STORE_INFO.get('art_imp', '00')}"
    ]
    for line in tax_info:
        story.append(Paragraph(line, normal_center))
    story.append(Spacer(1, 5*mm))
    
    # Document title (French, bold, bigger)
    story.append(Paragraph("FACTURE PROFORMA", ParagraphStyle(
        'doc_title', parent=bold_title, fontSize=14, textColor=colors.darkblue, spaceAfter=15
    )))
    
    # Horizontal line
    story.append(HRFlowable(width=A4[0]-30*mm, thickness=0.8, color=colors.black))
    story.append(Spacer(1, 8*mm))
    
    # ----- Customer & Invoice Details (two columns, French)-----
    customer_data = [
        [Paragraph("<b>Client :</b>", bold_left)],
        [Paragraph(f"Nom : {customer_info['name']}", normal_left)],
        [Paragraph(f"Téléphone : {customer_info['phone']}", normal_left)],
    ]
    customer_table = Table(customer_data, colWidths=[A4[0]*0.45 - 20*mm])
    customer_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    
    invoice_data = [
        [Paragraph("<b>Facture :</b>", bold_left)],
        [Paragraph(f"N° : {invoice_number}", normal_left)],
        [Paragraph(f"Date : {datetime.now().strftime('%d/%m/%Y')}", normal_left)],
    ]
    invoice_table = Table(invoice_data, colWidths=[A4[0]*0.45 - 20*mm])
    invoice_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    
    info_table = Table([[customer_table, invoice_table]], colWidths=[A4[0]*0.5, A4[0]*0.5])
    story.append(info_table)
    story.append(Spacer(1, 12*mm))
    
    # ----- Items Table (French headers) -----
    headers = [
        Paragraph("<b>#</b>", table_header),
        Paragraph("<b>Réf.</b>", table_header),
        Paragraph("<b>Désignation</b>", table_header),
        Paragraph("<b>Qté</b>", table_header),
        Paragraph("<b>Prix unit.</b>", table_header),
        Paragraph("<b>Total HT</b>", table_header),
    ]
    col_widths = [A4[0]*0.05, A4[0]*0.10, A4[0]*0.40, A4[0]*0.10, A4[0]*0.15, A4[0]*0.15]
    
    table_data = [headers]
    subtotal = 0.0
    for idx, item in enumerate(cart_items, start=1):
        line_total = item['quantity'] * item['price']
        subtotal += line_total
        ref = item.get('ref', '')
        table_data.append([
            Paragraph(str(idx), table_cell),
            Paragraph(ref, table_cell),
            Paragraph(item['title'], table_cell_left),
            Paragraph(str(item['quantity']), table_cell),
            Paragraph(f"{item['price']:.2f} DA", table_cell),
            Paragraph(f"{line_total:.2f} DA", table_cell),
        ])
    
    # Total row
    table_data.append([
        Paragraph("", table_cell), "", "",
        Paragraph("<b>TOTAL HT</b>", bold_left),
        "",
        Paragraph(f"<b>{subtotal:.2f} DA</b>", bold_left)
    ])
    
    items_table = Table(table_data, colWidths=col_widths)
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('ALIGN', (2,1), (2,-2), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('FONTSIZE', (0,1), (-1,-2), 9),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-2), 0.5, colors.lightgrey),
        ('LINEABOVE', (0,-1), (-1,-1), 1.5, colors.black),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#ecf0f1')),
        ('SPAN', (2,-1), (3,-1)),
    ]))
    story.append(items_table)

    doc.build(story)
    with Session(engine) as session:
        new_bill = models.Bill(
                file_name = output_path,
                type="proforma",
            )
        session.add(new_bill)
        session.commit()
    print(f"Proforma invoice saved to: {os.path.abspath(output_path)}")
    return output_path

@app.route('/api/print/proforma', methods=['POST'])
def print_proforma():
    data = request.json
    cart_items = data.get('items', [])
    
    try:
        assert data['customer'] != None
        customer_info = data.get('customer')
    except AssertionError:
        customer_info = {
                'name': 'Client',
                'phone': ''
            }
    invoice_number = data.get('invoice_number', '1')   # allow custom number
    
    if not cart_items:
        return jsonify({'error': 'No items in cart'}), 400
    
    pdf_path = build_proforma_pdf(cart_items, customer_info, invoice_number=invoice_number)
    os.startfile("/".join([os.getcwd(), pdf_path]), 'print')
    return jsonify({'success': True})

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
            'category_id': p.category_id,
            'quantity': p.quantity,
            'supplier_id': p.supplier_id,
            'item_per_box':  p.item_per_box,
            'box_price': p.box_price,
            'price': p.price,
            'cashbox_id': p.cashbox_id
        } for p in products])

@app.route('/api/products/add', methods=['POST'])
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
        return jsonify({'success': True, 'id': new_product.id, 'message': 'Product added successfully'})

@app.route('/api/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    data = request.json
    with Session(engine) as session:
        # Get the existing product
        product = session.get(models.Product, product_id)
        if not product:
            return jsonify({'success': False, 'message': 'Product not found'}), 404
        
        # Update fields if they exist in the request
        if 'title' in data:
            product.title = data['title']
        if 'barcode' in data:
            product.barcode = data['barcode']
        if 'quantity' in data:
            product.quantity = data['quantity']
        if 'price' in data:
            product.price = data['price']
        if 'category_id' in data:
            product.category_id = data['category_id']
        if 'supplier_id' in data:
            product.supplier_id = data['supplier_id']
        if 'item_per_box' in data:
            product.item_per_box = data['item_per_box']
        if 'box_price' in data:
            product.box_price = data['box_price']
        if 'cashbox_id' in data:
            product.cashbox_id = data['cashbox_id']
        
        session.commit()
        session.refresh(product)

        return jsonify({
            'success': True, 
            'id': product.id,
            'message': 'Product updated successfully'
        })

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
    
@app.route('/api/categories/<int:category_id>', methods=['DELETE'])
def remove_category(category_id):
    with Session(engine) as session:
        stmt = delete(models.Category).where(models.Category.id == category_id)
        session.exec(stmt)
        session.commit()
        return jsonify({'success': True})

@app.route('/api/categories/add', methods=['POST'])
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
            'address': s.address
        } for s in suppliers])

@app.route('/api/suppliers/add', methods=['POST'])
def add_supplier():
    data = request.json
    with Session(engine) as session:
        new_supplier = models.Supplier(
            name=data['name'],
            phone=data['phone'],
            address=data['address']
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

@app.route('/api/cashboxes/add', methods=['POST'])
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

@app.route('/api/cashboxes/remove/<int:cashbox_id>', methods=['DELETE'])
def remove_cashbox(cashbox_id):
    data = request.json
    with Session(engine) as session:
        stmt = delete(models.Cashbox).where(models.Cashbox.id == cashbox_id)
        session.exec(stmt)
        session.refresh(models.Cashbox)
        return jsonify({'success': True, 'id': cashbox.id})

@app.route('/api/cashboxes/<int:cashbox_id>', methods=['PUT'])
def update_cashbox(cashbox_id):
    data = request.json
    with Session(engine) as session:
        cashbox = session.get(models.Cashbox, cashbox_id)
        if not cashbox:
            return jsonify({'success': False, 'message': 'Cashbox not found'}), 404
        if 'drawer' in data:
            cashbox.title = data['title']
            cashbox.drawer = data['drawer']
        session.commit()
        return jsonify({'success': True})
    

# ==================== SETTINGS API ====================
@app.route('/api/settings', methods=['GET'])
def get_settings():
    with Session(engine) as session:
        settings = session.exec(select(models.Settings)).first()
        if not settings:
            # Create default settings if none exist
            settings = models.Settings()
            session.add(settings)
            session.commit()
            session.refresh(settings)
        return jsonify({
            'store_name': settings.store_name,
            'store_phone': settings.store_phone,
            'store_address': settings.store_address,
            'rc': settings.rc,
            'nif': settings.nif,
            'nis': settings.nis,
            'art_imp': settings.art_imp,
            'receipt_header': settings.receipt_header,
            'receipt_footer': settings.receipt_footer,
            'currency_symbol': settings.currency_symbol,
            'low_stock_threshold': settings.low_stock_threshold,
            'default_customer': settings.default_customer,
            'dark_mode': settings.dark_mode
        })

@app.route('/api/settings', methods=['PUT'])
def update_settings():
    data = request.json
    with Session(engine) as session:
        settings = session.exec(select(models.Settings)).first()
        if not settings:
            settings = models.Settings()
            session.add(settings)
        
        # Update fields
        settings.store_name = data['store_name']
        settings.store_phone = data['store_phone']
        settings.store_address = data['store_address']
        settings.rc = data['rc']
        settings.nif = data['nif']
        settings.nis = data['nis']
        settings.art_imp = data['art_imp']
        settings.receipt_header = data['receipt_header']
        settings.receipt_footer = data['receipt_footer']
        settings.currency_symbol = data['currency_symbol']
        settings.low_stock_threshold = data['low_stock_threshold']
        settings.default_customer = data['default_customer']
        settings.dark_mode = data['dark_mode']
        
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
    
@app.route('/api/customers/', methods=["PUT"])
def add_debt(): 
    data = request.json
    with Session(engine) as session:
        customer = session.get(models.Customer, data['customer_id'])
        for item in data['cart']:
            product = session.get(models.Product, item['id'])

            if product:
                product.quantity -= item['quantity']
            if customer:
                customer.debt += item['price'] * item['quantity']

            session.commit()
    return jsonify({'success': True})

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
                'box_price': product.box_price if product else None,
                'item_per_box': product.item_per_box if product else None,
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
        try:
            cashbox = session.get(models.Cashbox, product.cashbox_id)
            if cashbox:
                cashbox.drawer += data['total']
        except:
            print('Cashbox ERROR')
        
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
    for item in data['items']:
        with Session(engine) as session:
            # Create sale record
            new_sale = models.Sale(
                product_id = item["id"],
                quantity = item["quantity"],
                total = item["quantity"] * item["price"] 
            )
            session.add(new_sale)
            
            # Update product stock
            product = session.get(models.Product, item['id'])
            if product:
                product.quantity -= item["quantity"]

            # Update Drawer
            cashbox = session.get(models.Cashbox, product.cashbox_id)
            if cashbox:
                cashbox.drawer += item["quantity"] * item["price"] 

            #session.commit()
    bill_path = build_bill(data['items'], data['customer'])

    os.startfile("/".join([os.getcwd(), bill_path]), 'print')
    return jsonify({'success': True})

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

port = find_free_port()

def start_flask():
    app.run(port=port, debug=False)

if __name__ == "__main__":
    login = LoginForm()
    login.mainloop()