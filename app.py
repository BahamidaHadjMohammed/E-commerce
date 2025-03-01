from flask import Flask, render_template, request, redirect, url_for, session, send_file
import sqlite3
import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from datetime import datetime
import io

app = Flask(__name__)
app.secret_key = 'simple_ecommerce_key'

# Initialize database
def init_db():
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        price REAL NOT NULL,
        stock INTEGER NOT NULL
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY,
        order_date TEXT NOT NULL,
        total_amount REAL NOT NULL,
        items TEXT NOT NULL
    )''')
    
    # Insert sample products if none exist
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        products = [
            ('Laptop', 'High performance laptop', 999.99, 10),
            ('Smartphone', 'Latest smartphone model', 699.99, 20),
            ('Headphones', 'Noise cancelling headphones', 149.99, 30),
            ('Tablet', '10-inch tablet', 299.99, 15),
            ('Smartwatch', 'Fitness tracking smartwatch', 199.99, 25)
        ]
        cursor.executemany("INSERT INTO products (name, description, price, stock) VALUES (?, ?, ?, ?)", products)
    
    conn.commit()
    conn.close()

# Initialize shopping cart
def init_cart():
    if 'cart' not in session:
        session['cart'] = []

# Routes
@app.route('/')
def index():
    init_cart()
    conn = sqlite3.connect('inventory.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    conn.close()
    return render_template('index.html', products=products, cart_size=len(session['cart']))

@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):
    init_cart()
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    conn.close()
    
    if product:
        cart_item = {
            'id': product[0],
            'name': product[1],
            'price': product[2],
            'quantity': 1
        }
        
        # Check if product already in cart
        for item in session['cart']:
            if item['id'] == product_id:
                item['quantity'] += 1
                session.modified = True
                return redirect(url_for('cart'))
        
        session['cart'].append(cart_item)
        session.modified = True
    
    return redirect(url_for('cart'))

@app.route('/cart')
def cart():
    init_cart()
    total = sum(item['price'] * item['quantity'] for item in session['cart'])
    return render_template('cart.html', cart=session['cart'], total=total)

@app.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):
    init_cart()
    for i, item in enumerate(session['cart']):
        if item['id'] == product_id:
            del session['cart'][i]
            session.modified = True
            break
    return redirect(url_for('cart'))

@app.route('/checkout')
def checkout():
    init_cart()
    total = sum(item['price'] * item['quantity'] for item in session['cart'])
    # Here we add the Stripe Payment
    
    return render_template('checkout.html', total=total)

@app.route('/process_order', methods=['POST'])
def process_order():
    init_cart()
    if not session['cart']:
        return redirect(url_for('index'))
    
    # Calculate total
    total = sum(item['price'] * item['quantity'] for item in session['cart'])
    
    # Save order to database
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    
    # Update inventory
    for item in session['cart']:
        cursor.execute("UPDATE products SET stock = stock - ? WHERE id = ?", 
                      (item['quantity'], item['id']))
    
    # Save order
    order_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO orders (order_date, total_amount, items) VALUES (?, ?, ?)",
                  (order_date, total, json.dumps(session['cart'])))
    
    order_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    
    # Create invoice
    invoice_data = generate_invoice(order_id, order_date, session['cart'], total)
    
    # Clear cart
    session['cart'] = []
    session.modified = True
    
    return send_file(invoice_data, as_attachment=True, download_name=f"invoice_{order_id}.pdf")

def generate_invoice(order_id, order_date, cart_items, total):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    
    # Header
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, 750, " Invoice Paper ")
    
    # Invoice details
    p.setFont("Helvetica", 12)
    p.drawString(50, 720, f"Invoice #: {order_id}")
    p.drawString(50, 700, f"Date : {order_date}")
    
    # Table header
    p.drawString(50, 660, "Product")
    p.drawString(300, 660, "Qty")
    p.drawString(350, 660, "Price")
    p.drawString(450, 660, "Total")
    
    p.line(50, 650, 550, 650)
    
    # Items
    y = 630
    for item in cart_items:
        p.drawString(50, y, item['name'])
        p.drawString(300, y, str(item['quantity']))
        p.drawString(350, y, f"€ {item['price']:.2f} ")
        p.drawString(450, y, f"€ {item['price'] * item['quantity']:.2f} ")
        y -= 20
    
    # Total
    p.line(50, y-10, 550, y-10)
    p.setFont("Helvetica-Bold", 12)
    p.drawString(350, y-30, "Total:")
    p.drawString(450, y-30, f"€ {total:.2f} ")
    
    p.save()
    buffer.seek(0)
    return buffer

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
