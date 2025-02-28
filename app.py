from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, make_response
import sqlite3
import os
from werkzeug.utils import secure_filename
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.secret_key = 'supersecretkey'
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Connexion DB
def get_db_connection():
    conn = sqlite3.connect('inventory.db')
    conn.row_factory = sqlite3.Row
    return conn

# Initialisation DB
def init_db():
    conn = get_db_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS products (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT NOT NULL,
                      quantity INTEGER NOT NULL,
                      price INTEGER NOT NULL,
                      image TEXT
                   )''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products').fetchall()
    conn.close()
    cart = session.get('cart', {})
    return render_template('index.html', products=products, cart=cart)

@app.route('/add', methods=['POST'])
def add_product():
    name = request.form['name']
    quantity = request.form['quantity']
    price = request.form['price']
    image = request.files['image']
    image_filename = ''
    
    if image and allowed_file(image.filename):
        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        image_filename = filename
    
    if name and quantity.isdigit() and price.isdigit():
        conn = get_db_connection()
        conn.execute('INSERT INTO products (name, quantity, price, image) VALUES (?, ?, ?, ?)',
                     (name, int(quantity), int(price), image_filename))
        conn.commit()
        conn.close()
    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
def delete_product(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM products WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/add_to_cart/<int:id>')
def add_to_cart(id):
    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (id,)).fetchone()
    conn.close()
    
    if product:
        cart = session.get('cart', {})
        if str(id) in cart and cart[str(id)] < product['quantity']:
            cart[str(id)] += 1
        elif str(id) not in cart:
            cart[str(id)] = 1
        session['cart'] = cart
    return redirect(url_for('index'))

@app.route('/cart')
def view_cart():
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products').fetchall()
    conn.close()
    cart = session.get('cart', {})
    cart_items = []
    total = 0

    for product_id, quantity in cart.items():
        product = next((p for p in products if str(p['id']) == product_id), None)
        if product:
            cart_items.append({'id': product['id'], 'name': product['name'], 'quantity': quantity, 'price': product['price'], 'image': product['image']})
            total += product['price'] * quantity

    return render_template('cart.html', cart=cart_items, total=total)

@app.route('/remove_from_cart/<id>')
def remove_from_cart(id):
    cart = session.get('cart', {})
    if id in cart:
        del cart[id]
    session['cart'] = cart
    return redirect(url_for('view_cart'))

@app.route('/generate_invoice')
def generate_invoice():
    cart = session.get('cart', {})
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products').fetchall()
    conn.close()

    response = make_response()
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=invoice.pdf'

    pdf = canvas.Canvas(response.stream)
    pdf.drawString(100, 800, 'Facture')
    y = 780

    for product_id, quantity in cart.items():
        product = next((p for p in products if str(p['id']) == product_id), None)
        if product:
            pdf.drawString(100, y, f"{product['name']} x {quantity} - {product['price']} DA")
            y -= 20

    pdf.showPage()
    pdf.save()
    return response

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
