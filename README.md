
BudolBox - E-Commerce System

BudolBox is a full-stack e-commerce web application built with **Flask (Python)**, **SQLite**, and modern HTML/CSS templates.  
It features user authentication, product management, shopping carts, order processing, and role-based dashboards for **customers** and **admins**.

---

## Features

User Features
- Register and login with secure password hashing.
- Browse products by category with **search and filter**.
- Add products to cart and proceed to **checkout**.
- View **order history** and account details.
- See **recently viewed products** (browsing history).
- Account settings with option to change password.

## Admin Features
- Access to **Admin Dashboard**.
- Manage products (add, edit, delete, activate/deactivate).
- Manage categories and inventory stock.
- Process orders in a **queue system**.
- Manage users (view customer info, orders, spending).
- Export data for reporting.

### Technical Highlights
- **SQLite** database with automatic initialization.
- Passwords stored securely via **SHA-256 hashing**.
- **Custom Data Structures** used in backend:
  - Linked List → Browsing History  
  - Tree → Category Hierarchy  
  - Queue → Order Processing  
  - Hash Table → User browsing session cache  
- **Email Notification Service** (simulated via console logs).
- **Responsive UI** using Font Awesome + custom CSS.

---

## Project Structure

```
project/
│── app.py                # Main Flask application
│── check_db.py           # Utility for inspecting and debugging database
│── instance/
│   └── ecommerce.db      # SQLite database (auto-created on first run)
│
├── templates/            # HTML templates
│   ├── index.html        # Landing page
│   ├── login.html        # Login page
│   ├── register.html     # Registration page
│   ├── customer_dashboard.html  # Customer UI
│   ├── admin_dashboard.html     # Admin UI
│   ├── account.html      # Account settings page
│
├── static/
│   ├── css/style.css     # Custom styles
│   ├── images/           # Uploaded product images
│
└── README.md             # Project documentation
```

---

## Database Schema

The database (`ecommerce.db`) includes the following tables:

- **users**
  - id, username, email, password_hash, role (admin/customer), created_at
- **products**
  - id, name, description, price, stock, category_id, image_path, is_active
- **categories**
  - id, name, parent_id
- **orders**
  - id, user_id, total_amount, status, shipping_address, contact_number, notes, created_at
- **order_items**
  - id, order_id, product_id, quantity, price
- **cart_items**
  - id, user_id, product_id, quantity, created_at

👉 Run `python check_db.py` to inspect tables, sample data, or run custom queries.

---

## Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/dc4ndre/ecommerce_website.git
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate     # macOS/Linux
venv\Scripts\activate      # Windows
```

### 3. Install Dependencies
```bash
pip install flask werkzeug
```

### 4. Run the App
```bash
python app.py
```
The app will start at **http://127.0.0.1:5000/**.

### 5. Admin Access
Default admin credentials are created on first run:
```
Username: admin
Email: admin@ecommerce.com
Password: admin123
```

---

## Usage

- **Homepage** → `/`
- **Register** → `/register`
- **Login** → `/login`
- **Customer Dashboard** → `/dashboard`
- **Admin Dashboard** → `/admin`
- **Account Settings** → `/account`

---

## 🛠Development Notes

- The system uses a **modular OOP design** with `DatabaseManager`, `EmailService`, and data structure classes inside `app.py`.
- For product images, uploads are stored in `static/images/`.
- The project demonstrates practical usage of **algorithms and data structures in web development**.

---

## 🔮 Future Improvements

- Enable real email notifications via SMTP (currently simulated).
- Add payment gateway integration.
- Improve reporting and analytics.
- Add product reviews and ratings.
- Deploy to a cloud server (Heroku, Render, etc.).
