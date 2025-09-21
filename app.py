from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
import sqlite3
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import threading
import time
import os
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key_here_change_this'

# Create instance directory for database
INSTANCE_PATH = os.path.join(os.path.dirname(__file__), 'instance')
os.makedirs(INSTANCE_PATH, exist_ok=True)

# Configure paths
app.config['DATABASE_PATH'] = os.path.join(INSTANCE_PATH, 'ecommerce.db')
app.config['UPLOAD_FOLDER'] = 'static/images'

# Create upload directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Helper function to format prices in pesos
def format_peso(amount):
    return f"₱{amount:,.2f}"

# Add template filter for peso formatting
@app.template_filter('peso')
def peso_filter(amount):
    return format_peso(float(amount))

# Data Structures Implementation

class Node:
    """Node for Linked List - used for browsing history"""
    def __init__(self, product_id, product_name, image_path=None, price=None, timestamp=None):
        self.product_id = product_id
        self.product_name = product_name
        self.image_path = image_path or ''
        self.price = price or 0
        self.timestamp = timestamp or datetime.now().isoformat()
        self.next = None

class BrowsingHistory:
    """Linked List implementation for browsing history"""
    def __init__(self, max_size=5):
        self.head = None
        self.max_size = max_size
        self.size = 0
    
    def add_product(self, product_id, product_name, image_path=None, price=None):
        # Remove if already exists
        self.remove_product(product_id)
        
        new_node = Node(product_id, product_name, image_path, price)
        new_node.next = self.head
        self.head = new_node
        self.size += 1
        
        # Keep only max_size items
        if self.size > self.max_size:
            self._remove_last()
    
    def remove_product(self, product_id):
        if not self.head:
            return
        
        if self.head.product_id == product_id:
            self.head = self.head.next
            self.size -= 1
            return
        
        current = self.head
        while current.next:
            if current.next.product_id == product_id:
                current.next = current.next.next
                self.size -= 1
                break
            current = current.next
    
    def _remove_last(self):
        if not self.head:
            return
        if not self.head.next:
            self.head = None
            self.size = 0
            return
        
        current = self.head
        while current.next.next:
            current = current.next
        current.next = None
        self.size -= 1
    
    def get_history(self):
        history = []
        current = self.head
        while current:
            history.append({
                'product_id': current.product_id,
                'product_name': current.product_name,
                'image_path': current.image_path,
                'price': current.price,
                'timestamp': current.timestamp
            })
            current = current.next
        return history
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'items': self.get_history(),
            'size': self.size,
            'max_size': self.max_size
        }

class CategoryNode:
    """Tree Node for product categories"""
    def __init__(self, category_id, name, parent=None):
        self.category_id = category_id
        self.name = name
        self.parent = parent
        self.children = []
        self.products = []
    
    def add_child(self, child_node):
        child_node.parent = self
        self.children.append(child_node)
    
    def add_product(self, product_id):
        if product_id not in self.products:
            self.products.append(product_id)

class CategoryTree:
    """Tree implementation for product categories"""
    def __init__(self):
        self.root = CategoryNode(0, "All Categories")
        self.categories = {0: self.root}
    
    def add_category(self, category_id, name, parent_id=0):
        parent = self.categories.get(parent_id, self.root)
        new_category = CategoryNode(category_id, name, parent)
        parent.add_child(new_category)
        self.categories[category_id] = new_category
        return new_category
    
    def get_category(self, category_id):
        return self.categories.get(category_id)
    
    def get_all_products_in_category(self, category_id):
        category = self.categories.get(category_id)
        if not category:
            return []
        
        products = category.products.copy()
        # Add products from subcategories
        for child in category.children:
            products.extend(self.get_all_products_in_category(child.category_id))
        
        return products
    
    def to_dict(self):
        """Convert tree to dictionary for JSON"""
        def node_to_dict(node):
            return {
                'id': node.category_id,
                'name': node.name,
                'children': [node_to_dict(child) for child in node.children],
                'product_count': len(node.products)
            }
        
        return node_to_dict(self.root)

class OrderQueue:
    """Queue implementation for order processing"""
    def __init__(self):
        self.orders = []
    
    def enqueue(self, order):
        self.orders.append(order)
    
    def dequeue(self):
        if self.orders:
            return self.orders.pop(0)
        return None
    
    def peek(self):
        if self.orders:
            return self.orders[0]
        return None
    
    def is_empty(self):
        return len(self.orders) == 0
    
    def size(self):
        return len(self.orders)
    
    def get_all_orders(self):
        return self.orders.copy()

class CartStack:
    """Stack implementation for shopping cart"""
    def __init__(self):
        self.items = []  # Stack of {'product_id': id, 'quantity': qty}
    
    def push(self, product_id, quantity):
        # Check if product already exists
        for item in self.items:
            if item['product_id'] == product_id:
                item['quantity'] += quantity
                return
        self.items.append({'product_id': product_id, 'quantity': quantity})
    
    def pop(self):
        if self.items:
            return self.items.pop()
        return None
    
    def peek(self):
        if self.items:
            return self.items[-1]
        return None
    
    def remove_product(self, product_id):
        self.items = [item for item in self.items if item['product_id'] != product_id]
    
    def update_quantity(self, product_id, quantity):
        for item in self.items:
            if item['product_id'] == product_id:
                if quantity <= 0:
                    self.remove_product(product_id)
                else:
                    item['quantity'] = quantity
                break
    
    def get_cart_items(self):
        return self.items.copy()
    
    def clear(self):
        self.items = []
    
    def get_total_items(self):
        return sum(item['quantity'] for item in self.items)
    
    def to_dict(self):
        return {
            'items': self.items,
            'total_items': self.get_total_items()
        }

# Database Manager
class DatabaseManager:
    def __init__(self, db_path=None):
        self.db_path = db_path or app.config['DATABASE_PATH']
        self.init_database()
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) DEFAULT 'customer',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Products table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                price DECIMAL(10,2) NOT NULL,
                stock INTEGER NOT NULL,
                category_id INTEGER DEFAULT 1,
                image_path VARCHAR(255),
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Categories table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(50) NOT NULL,
                parent_id INTEGER DEFAULT 0
            )
        ''')
        
        # Orders table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                total_amount DECIMAL(10,2),
                status VARCHAR(20) DEFAULT 'pending',
                shipping_address TEXT,
                contact_number VARCHAR(20),
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Order items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                product_id INTEGER,
                quantity INTEGER,
                price DECIMAL(10,2),
                FOREIGN KEY (order_id) REFERENCES orders(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        ''')
        
        # Create default admin user
        admin_password = self.hash_password("admin123")
        cursor.execute('''
            INSERT OR IGNORE INTO users (username, email, password_hash, role)
            VALUES (?, ?, ?, ?)
        ''', ("admin", "admin@ecommerce.com", admin_password, "admin"))
        
        # Create default categories
        default_categories = [
            (1, "Electronics", 0),
            (2, "Clothing", 0),
            (3, "Books", 0),
            (4, "Home & Garden", 0),
            (5, "Smartphones", 1),
            (6, "Laptops", 1)
        ]
        
        for cat_id, name, parent_id in default_categories:
            cursor.execute('''
                INSERT OR IGNORE INTO categories (id, name, parent_id)
                VALUES (?, ?, ?)
            ''', (cat_id, name, parent_id))
        
        conn.commit()
        conn.close()
    
    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()
    
    def execute_query(self, query, params=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        result = cursor.fetchall()
        conn.commit()
        conn.close()
        return result
    
    def execute_insert(self, query, params):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(query, params)
        last_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return last_id

# Email Service
class EmailService:
    def __init__(self):
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.admin_email = "your_email@gmail.com"  # Configure this
        self.admin_password = "your_app_password"  # Configure this
    
    def send_order_status_email(self, customer_email, order_id, status, expected_delivery=None):
        try:
            msg = MIMEMultipart()
            msg['From'] = self.admin_email
            msg['To'] = customer_email
            msg['Subject'] = f"Order #{order_id} Status Update"
            
            body = f"""
            Dear Valued Customer,
            
            Your order #{order_id} status has been updated to: {status.upper()}
            
            """
            
            if expected_delivery:
                body += f"Expected Delivery Date: {expected_delivery}\n"
            
            body += """
            Thank you for shopping with us!
            
            Best regards,
            BudolBox Team
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Comment out actual email sending for development
            print(f"Email sent to {customer_email} for order {order_id}: {status}")
            return True
        except Exception as e:
            print(f"Email sending failed: {e}")
            return False

# Initialize global objects
db = DatabaseManager()
email_service = EmailService()
category_tree = CategoryTree()
order_queue = OrderQueue()

# Load categories into tree and add ALL products to each category
def load_categories():
    categories = db.execute_query("SELECT id, name, parent_id FROM categories ORDER BY parent_id, id")
    for cat_id, name, parent_id in categories:
        category_tree.add_category(cat_id, name, parent_id)
    
    # Load products into categories
    products = db.execute_query("SELECT id, category_id FROM products WHERE is_active = 1")
    for product_id, category_id in products:
        category_node = category_tree.get_category(category_id)
        if category_node:
            category_node.add_product(product_id)
        
        # IMPORTANT: Add ALL products to the root "All Categories" node
        root_category = category_tree.get_category(0)
        if root_category:
            root_category.add_product(product_id)

load_categories()

# Session management using hash table concept
user_sessions = {}  # Hash table for session management
user_browsing_history = {}  # Hash table for user browsing histories
user_carts = {}  # Hash table for user shopping carts

# File upload configuration
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Routes

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'success': False, 'message': 'Please fill in all fields'})
        
        # Hash password for comparison (Hash table lookup concept)
        password_hash = db.hash_password(password)
        
        user_data = db.execute_query(
            "SELECT id, username, email, role FROM users WHERE (username = ? OR email = ?) AND password_hash = ?",
            (username, username, password_hash)
        )
        
        if user_data:
            user_id, username, email, role = user_data[0]
            
            # Store in session (Hash table concept)
            session['user_id'] = user_id
            session['username'] = username
            session['email'] = email
            session['role'] = role
            
            # Initialize user-specific data structures
            if user_id not in user_browsing_history:
                user_browsing_history[user_id] = BrowsingHistory()
            if user_id not in user_carts:
                user_carts[user_id] = CartStack()
            
            return jsonify({
                'success': True, 
                'role': role,
                'redirect': '/admin' if role == 'admin' else '/dashboard'
            })
        else:
            return jsonify({'success': False, 'message': 'Invalid username/email or password'})
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json()
        email = data.get('email')
        username = data.get('username')
        password = data.get('password')
        confirm_password = data.get('confirm_password')
        
        if not all([email, username, password, confirm_password]):
            return jsonify({'success': False, 'message': 'Please fill in all fields'})
        
        if password != confirm_password:
            return jsonify({'success': False, 'message': 'Passwords do not match'})
        
        if len(password) < 6:
            return jsonify({'success': False, 'message': 'Password must be at least 6 characters'})
        
        # Check if user already exists (Hash table lookup concept)
        existing_user = db.execute_query(
            "SELECT id FROM users WHERE username = ? OR email = ?",
            (username, email)
        )
        
        if existing_user:
            return jsonify({'success': False, 'message': 'Username or email already exists'})
        
        # Create new user
        password_hash = db.hash_password(password)
        try:
            user_id = db.execute_insert(
                "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                (username, email, password_hash, 'customer')
            )
            return jsonify({'success': True, 'message': 'Registration successful! Please login.'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'Registration failed: {str(e)}'})
    
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session['role'] != 'customer':
        return redirect(url_for('admin_dashboard'))
    
    return render_template('customer_dashboard.html', user=session)

@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    return render_template('admin_dashboard.html', user=session)

@app.route('/api/products')
def get_products():
    category_id = request.args.get('category_id', type=int)
    search_query = request.args.get('search', '')
    
    if search_query:
        products = db.execute_query('''
            SELECT p.id, p.name, p.description, p.price, p.stock, p.image_path, c.name as category
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.is_active = 1 AND (p.name LIKE ? OR p.description LIKE ?)
            ORDER BY p.name
        ''', (f'%{search_query}%', f'%{search_query}%'))
    elif category_id is not None:
        # Handle "All Categories" (category_id = 0) to show ALL products
        if category_id == 0:
            products = db.execute_query('''
                SELECT p.id, p.name, p.description, p.price, p.stock, p.image_path, c.name as category
                FROM products p
                LEFT JOIN categories c ON p.category_id = c.id
                WHERE p.is_active = 1
                ORDER BY p.name
            ''')
        else:
            # Get all products in category and subcategories using tree structure
            product_ids = category_tree.get_all_products_in_category(category_id)
            if product_ids:
                placeholders = ','.join('?' for _ in product_ids)
                products = db.execute_query(f'''
                    SELECT p.id, p.name, p.description, p.price, p.stock, p.image_path, c.name as category
                    FROM products p
                    LEFT JOIN categories c ON p.category_id = c.id
                    WHERE p.is_active = 1 AND p.id IN ({placeholders})
                    ORDER BY p.name
                ''', product_ids)
            else:
                products = []
    else:
        products = db.execute_query('''
            SELECT p.id, p.name, p.description, p.price, p.stock, p.image_path, c.name as category
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.is_active = 1
            ORDER BY p.name
        ''')
    
    # Convert to list of dictionaries with peso formatting
    products_list = []
    for product in products:
        products_list.append({
            'id': product[0],
            'name': product[1],
            'description': product[2],
            'price': product[3],
            'price_formatted': format_peso(product[3]),
            'stock': product[4],
            'image_path': product[5],
            'category': product[6]
        })
    
    return jsonify(products_list)

@app.route('/api/categories')
def get_categories():
    return jsonify(category_tree.to_dict())

@app.route('/api/product/<int:product_id>')
def get_product(product_id):
    if 'user_id' in session:
        user_id = session['user_id']
        
        # Add to browsing history with complete product info (Linked List operation)
        product_data = db.execute_query(
            "SELECT name, price, image_path FROM products WHERE id = ?", (product_id,)
        )
        
        if product_data and user_id in user_browsing_history:
            product_name, price, image_path = product_data[0]
            user_browsing_history[user_id].add_product(product_id, product_name, image_path, price)
    
    # Get product details
    product = db.execute_query('''
        SELECT p.id, p.name, p.description, p.price, p.stock, p.image_path, c.name as category
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.id = ?
    ''', (product_id,))
    
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    
    product_data = {
        'id': product[0][0],
        'name': product[0][1],
        'description': product[0][2],
        'price': product[0][3],
        'price_formatted': format_peso(product[0][3]),
        'stock': product[0][4],
        'image_path': product[0][5],
        'category': product[0][6]
    }
    
    # Get recommendations (same category)
    recommendations = db.execute_query('''
        SELECT id, name, price, image_path
        FROM products
        WHERE category_id = (SELECT category_id FROM products WHERE id = ?) 
        AND id != ? AND is_active = 1
        LIMIT 3
    ''', (product_id, product_id))
    
    product_data['recommendations'] = [
        {
            'id': rec[0],
            'name': rec[1],
            'price': rec[2],
            'price_formatted': format_peso(rec[2]),
            'image_path': rec[3]
        } for rec in recommendations
    ]
    
    return jsonify(product_data)

@app.route('/api/browsing_history')
def get_browsing_history():
    if 'user_id' not in session:
        return jsonify([])
    
    user_id = session['user_id']
    if user_id in user_browsing_history:
        history_data = user_browsing_history[user_id].to_dict()
        # Format prices in history
        for item in history_data['items']:
            item['price_formatted'] = format_peso(item['price']) if item['price'] else '₱0.00'
        return jsonify(history_data)
    
    return jsonify({'items': [], 'size': 0, 'max_size': 5})

@app.route('/api/cart', methods=['GET', 'POST', 'PUT', 'DELETE'])
def manage_cart():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    user_id = session['user_id']

    if request.method == 'GET':
        # Fetch cart items from DB
        cart_items = db.execute_query('''
            SELECT ci.product_id, ci.quantity, p.name, p.price, p.image_path
            FROM cart_items ci
            JOIN products p ON ci.product_id = p.id
            WHERE ci.user_id = ?
        ''', (user_id,))

        detailed_items = []
        total = 0

        for product_id, qty, name, price, image_path in cart_items:
            subtotal = price * qty
            total += subtotal
            detailed_items.append({
                'product_id': product_id,
                'name': name,
                'price': price,
                'price_formatted': format_peso(price),
                'quantity': qty,
                'subtotal': subtotal,
                'subtotal_formatted': format_peso(subtotal),
                'image_path': image_path
            })

        return jsonify({
            'items': detailed_items,
            'total': total,
            'total_formatted': format_peso(total),
            'item_count': sum(item['quantity'] for item in detailed_items)
        })

    elif request.method == 'POST':
        data = request.get_json()
        product_id = data.get('product_id')
        quantity = data.get('quantity', 1)

        # Check if product already exists in cart
        existing = db.execute_query('''
            SELECT id, quantity FROM cart_items
            WHERE user_id = ? AND product_id = ?
        ''', (user_id, product_id))

        if existing:
            new_qty = existing[0][1] + quantity
            db.execute_query('''
                UPDATE cart_items SET quantity = ? WHERE id = ?
            ''', (new_qty, existing[0][0]))
        else:
            db.execute_insert('''
                INSERT INTO cart_items (user_id, product_id, quantity)
                VALUES (?, ?, ?)
            ''', (user_id, product_id, quantity))

        return jsonify({'success': True, 'message': 'Product added to cart'})

    elif request.method == 'PUT':
        data = request.get_json()
        product_id = data.get('product_id')
        quantity = data.get('quantity')

        if quantity <= 0:
            db.execute_query('DELETE FROM cart_items WHERE user_id = ? AND product_id = ?', (user_id, product_id))
        else:
            db.execute_query('''
                UPDATE cart_items SET quantity = ?
                WHERE user_id = ? AND product_id = ?
            ''', (quantity, user_id, product_id))

        return jsonify({'success': True, 'message': 'Cart updated'})

    elif request.method == 'DELETE':
        data = request.get_json()
        if data.get('clear_all'):
            db.execute_query('DELETE FROM cart_items WHERE user_id = ?', (user_id,))
            return jsonify({'success': True, 'message': 'Cart cleared'})

        product_id = data.get('product_id')
        if product_id:
            db.execute_query('DELETE FROM cart_items WHERE user_id = ? AND product_id = ?', (user_id, product_id))
            return jsonify({'success': True, 'message': 'Item removed from cart'})

@app.route('/api/checkout', methods=['POST'])
def checkout():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user_id = session['user_id']
    data = request.get_json()
    
    address = data.get('address')
    contact = data.get('contact')
    notes = data.get('notes', '')
    
    if not address or not contact:
        return jsonify({'success': False, 'message': 'Address and contact are required'})
    
    # ✅ Fetch cart items from the DB instead of user_carts
    cart_items = db.execute_query('''
        SELECT ci.product_id, ci.quantity, p.price
        FROM cart_items ci
        JOIN products p ON ci.product_id = p.id
        WHERE ci.user_id = ?
    ''', (user_id,))
    
    if not cart_items:
        return jsonify({'success': False, 'message': 'Cart is empty'})
    
    try:
        # Calculate total
        total = sum(price * qty for product_id, qty, price in cart_items)
        
        # Create order
        order_id = db.execute_insert('''
            INSERT INTO orders (user_id, total_amount, status, shipping_address, contact_number, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, total, 'pending', address, contact, notes))
        
        # Add order items & update stock
        for product_id, qty, price in cart_items:
            db.execute_insert('''
                INSERT INTO order_items (order_id, product_id, quantity, price)
                VALUES (?, ?, ?, ?)
            ''', (order_id, product_id, qty, price))
            
            db.execute_query('''
                UPDATE products SET stock = stock - ? WHERE id = ?
            ''', (qty, product_id))
        
        # Clear DB cart after checkout
        db.execute_query('DELETE FROM cart_items WHERE user_id = ?', (user_id,))
        
        # Add to order processing queue
        order_data = {
            'id': order_id,
            'user_id': user_id,
            'total': total,
            'status': 'pending'
        }
        order_queue.enqueue(order_data)
        
        return jsonify({
            'success': True, 
            'message': f'Order #{order_id} placed successfully! Total: {format_peso(total)}',
            'order_id': order_id,
            'total_formatted': format_peso(total)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to place order: {str(e)}'})

# Admin routes
@app.route('/api/admin/products')
def admin_get_products():
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    products = db.execute_query('''
        SELECT p.id, p.name, p.description, p.price, p.stock,
               p.category_id, c.name, p.is_active, p.image_path
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        ORDER BY p.id DESC
    ''')
    
    products_list = []
    for product in products:
        products_list.append({
            'id': product[0],
            'name': product[1],
            'description': product[2],
            'price': product[3],
            'price_formatted': format_peso(product[3]),
            'stock': product[4],
            'category_id': product[5],
            'category': product[6] or 'Uncategorized',
            'is_active': bool(product[7]),
            'image_path': product[8] or ''
        })
    
    return jsonify(products_list)


@app.route('/api/admin/orders')
def admin_get_orders():
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    orders = db.execute_query('''
        SELECT o.id, u.username, u.email, o.total_amount, o.status, 
               o.shipping_address, o.contact_number, o.created_at
        FROM orders o
        JOIN users u ON o.user_id = u.id
        ORDER BY o.created_at DESC
    ''')
    
    orders_list = []
    for order in orders:
        orders_list.append({
            'id': order[0],
            'customer': order[1],
            'email': order[2],
            'total': order[3],
            'total_formatted': format_peso(order[3]),
            'status': order[4],
            'address': order[5],
            'contact': order[6],
            'date': order[7]
        })
    
    return jsonify(orders_list)

@app.route('/api/admin/orders/<int:order_id>/status', methods=['PUT'])
def update_order_status(order_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    new_status = data.get('status')
    expected_delivery = data.get('expected_delivery', '')
    
    try:
        # Get customer email
        customer_data = db.execute_query('''
            SELECT u.email FROM users u
            JOIN orders o ON u.id = o.user_id
            WHERE o.id = ?
        ''', (order_id,))
        
        if not customer_data:
            return jsonify({'success': False, 'message': 'Order not found'})
        
        customer_email = customer_data[0][0]
        
        # Update order status
        db.execute_query(
            "UPDATE orders SET status = ? WHERE id = ?",
            (new_status, order_id)
        )
        
        # Send email notification
        email_sent = email_service.send_order_status_email(
            customer_email, order_id, new_status, expected_delivery
        )
        
        return jsonify({
            'success': True,
            'message': f'Order status updated to {new_status}'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/admin/process_orders', methods=['POST'])
def process_orders():
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    if order_queue.is_empty():
        return jsonify({'message': 'No orders in processing queue'})
    
    order = order_queue.dequeue()
    
    def process_order_async():
        # Simulate processing with 5-second intervals
        statuses = ['processing', 'shipping', 'delivered']
        
        for i, status in enumerate(statuses):
            time.sleep(5)  # 5-second delay as specified
            
            try:
                db.execute_query(
                    "UPDATE orders SET status = ? WHERE id = ?",
                    (status, order['id'])
                )
                print(f"Order {order['id']} status updated to {status}")
            except Exception as e:
                print(f"Error updating order {order['id']}: {e}")
    
    # Start processing in background
    threading.Thread(target=process_order_async, daemon=True).start()
    
    return jsonify({
        'success': True,
        'message': f'Processing Order #{order["id"]} (Total: {format_peso(order["total"])})'
    })

@app.route('/api/admin/users')
def admin_get_users():
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    users = db.execute_query('''
        SELECT u.id, u.username, u.email, u.role, u.created_at,
               COUNT(o.id) as order_count,
               COALESCE(SUM(o.total_amount), 0) as total_spent
        FROM users u
        LEFT JOIN orders o ON u.id = o.user_id
        WHERE u.role = 'customer'
        GROUP BY u.id, u.username, u.email, u.role, u.created_at
        ORDER BY u.created_at DESC
    ''')
    
    users_list = []
    for user in users:
        users_list.append({
            'id': user[0],
            'username': user[1],
            'email': user[2],
            'role': user[3],
            'created_at': user[4],
            'order_count': user[5],
            'total_spent': user[6],
            'total_spent_formatted': format_peso(user[6])
        })
    
    return jsonify(users_list)

@app.route('/api/admin/users/<int:user_id>/transactions')
def get_user_transactions(user_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    transactions = db.execute_query('''
        SELECT o.id, o.created_at, o.total_amount, o.status,
               COUNT(oi.id) as item_count
        FROM orders o
        LEFT JOIN order_items oi ON o.id = oi.order_id
        WHERE o.user_id = ?
        GROUP BY o.id, o.created_at, o.total_amount, o.status
        ORDER BY o.created_at DESC
    ''', (user_id,))
    
    transactions_list = []
    total_spent = 0
    
    for transaction in transactions:
        total_spent += transaction[2]
        transactions_list.append({
            'order_id': transaction[0],
            'date': transaction[1],
            'total': transaction[2],
            'total_formatted': format_peso(transaction[2]),
            'status': transaction[3],
            'item_count': transaction[4]
        })
    
    return jsonify({
        'transactions': transactions_list,
        'total_spent': total_spent,
        'total_spent_formatted': format_peso(total_spent),
        'total_orders': len(transactions_list)
    })

@app.route('/api/admin/products', methods=['POST'])
def admin_add_product():
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    
    try:
        product_id = db.execute_insert('''
            INSERT INTO products (name, description, price, stock, category_id, is_active, image_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['name'],
            data['description'],
            float(data['price']),
            int(data['stock']),
            int(data['category_id']),
            bool(data['is_active']),
            data.get('image_path', '')
        ))
        
        # Add to category tree
        category_node = category_tree.get_category(int(data['category_id']))
        if category_node:
            category_node.add_product(product_id)
        
        # Add to "All Categories" root node
        root_category = category_tree.get_category(0)
        if root_category:
            root_category.add_product(product_id)
        
        return jsonify({'success': True, 'product_id': product_id})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/admin/products/<int:product_id>', methods=['GET'])
def admin_get_product(product_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    product = db.execute_query('''
        SELECT id, name, description, price, stock, category_id, image_path, is_active
        FROM products
        WHERE id = ?
    ''', (product_id,))
    
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    
    product_data = {
        'id': product[0][0],
        'name': product[0][1],
        'description': product[0][2],
        'price': product[0][3],
        'price_formatted': format_peso(product[0][3]),
        'stock': product[0][4],
        'category_id': product[0][5],
        'image_path': product[0][6],
        'is_active': bool(product[0][7])
    }
    
    return jsonify(product_data)

@app.route('/api/admin/products/<int:product_id>', methods=['PUT'])
def admin_update_product(product_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    
    try:
        db.execute_query('''
            UPDATE products 
            SET name = ?, description = ?, price = ?, stock = ?, 
                category_id = ?, is_active = ?, image_path = ?
            WHERE id = ?
        ''', (
            data['name'],
            data['description'],
            float(data['price']),
            int(data['stock']),
            int(data['category_id']),
            bool(data['is_active']),
            data.get('image_path', ''),
            product_id
        ))
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/admin/products/<int:product_id>', methods=['DELETE'])
def admin_delete_product(product_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        db.execute_query("DELETE FROM products WHERE id = ?", (product_id,))
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/account')
def account():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user_data = db.execute_query(
        "SELECT id, username, email, role, created_at FROM users WHERE id = ?",
        (user_id,)
    )

    if not user_data:
        return redirect(url_for('login'))

    user = {
        "id": user_data[0][0],
        "username": user_data[0][1],
        "email": user_data[0][2],
        "role": user_data[0][3],
        "created_at": str(user_data[0][4])  # send as string
    }

    return render_template("account.html", user=user)


@app.route('/api/account', methods=['PUT'])
def update_account():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.get_json()
    user_id = session['user_id']
    
    new_username = data.get('username')
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    if not current_password:
        return jsonify({'success': False, 'message': 'Current password required'})
    
    # Verify current password
    current_hash = db.hash_password(current_password)
    user_check = db.execute_query(
        "SELECT id FROM users WHERE id = ? AND password_hash = ?",
        (user_id, current_hash)
    )
    
    if not user_check:
        return jsonify({'success': False, 'message': 'Current password is incorrect'})
    
    # Check if new username is available
    if new_username != session['username']:
        existing = db.execute_query(
            "SELECT id FROM users WHERE username = ? AND id != ?",
            (new_username, user_id)
        )
        if existing:
            return jsonify({'success': False, 'message': 'Username already taken'})
    
    try:
        # Update username
        db.execute_query(
            "UPDATE users SET username = ? WHERE id = ?",
            (new_username, user_id)
        )
        
        # Update password if provided
        if new_password:
            if len(new_password) < 6:
                return jsonify({'success': False, 'message': 'New password must be at least 6 characters'})
            
            new_hash = db.hash_password(new_password)
            db.execute_query(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (new_hash, user_id)
            )
        
        # Update session
        session['username'] = new_username
        
        return jsonify({'success': True, 'message': 'Account updated successfully!'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Update failed: {str(e)}'})

@app.route('/api/orders')
def get_user_orders():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user_id = session['user_id']
    orders = db.execute_query('''
        SELECT id, total_amount, status, created_at
        FROM orders
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 10
    ''', (user_id,))
    
    orders_list = []
    for order in orders:
        orders_list.append({
            'id': order[0],
            'total': order[1],
            'total_formatted': format_peso(order[1]),
            'status': order[2],
            'date': order[3]
        })
    
    return jsonify(orders_list)

# Image upload route with unique filename generation
@app.route('/upload_image', methods=['POST'])
def upload_image():
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file selected'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'})
    
    if file and allowed_file(file.filename):
        # Create unique filename with timestamp, UUID, and original name
        original_filename = secure_filename(file.filename)
        file_extension = original_filename.rsplit('.', 1)[1].lower()
        timestamp = str(int(time.time()))
        unique_id = str(uuid.uuid4())[:8]
        unique_filename = f"{timestamp}_{unique_id}_{original_filename}"
        
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        
        return jsonify({
            'success': True, 
            'filename': unique_filename,
            'url': f'/static/images/{unique_filename}'
        })
    
    return jsonify({'success': False, 'message': 'Invalid file type. Please upload PNG, JPG, JPEG, or GIF files.'})

# Serve uploaded images
@app.route('/static/images/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)