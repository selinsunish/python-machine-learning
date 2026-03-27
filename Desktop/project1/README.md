# College Resale (Flask + MongoDB)

A beginner-friendly web app where students can list products, browse products, add items to cart, and complete a dummy payment flow.

## Features

- User signup and login
- Password hashing using `flask-bcrypt`
- Session-based authentication
- Add and view products
- Cart system per logged-in user
- Checkout and dummy payment
- MongoDB integration with `products`, `users`, and `carts` collections

## Project Structure

```text
college-resale - Copy/
├── app.py
├── requirements.txt
├── README.md
└── templates/
    ├── index.html
    ├── add.html
    ├── login.html
    ├── signup.html
    ├── cart.html
    └── payment.html
```

## Requirements

- Python 3.8+
- MongoDB Atlas (or any MongoDB connection URI)

## Installation

1. Open terminal in project folder:
   - `cd "c:\Users\jacob\Desktop\college-resale - Copy"`
2. Install dependencies:
   - `pip install -r requirements.txt`

## Configuration

Set environment variables (optional, recommended):

- `MONGO_URI` -> your MongoDB URI
- `MONGO_DB` -> database name (default: `college_resale`)
- `FLASK_SECRET_KEY` -> session secret key
- `PORT` -> app port (default: `5000`)

If `MONGO_URI` is not set, app uses the URI currently present in `app.py`.

## Run the App

- `python app.py`

Then open:
- `http://127.0.0.1:5000`

## Main Routes

- `/` -> product listing page
- `/signup` -> create account
- `/login` -> login page
- `/logout` -> logout user
- `/add` -> add new product (logged-in users)
- `/add_to_cart/<product_id>` -> add product to cart
- `/cart` -> view cart items and total
- `/checkout` -> checkout page
- `/pay` -> dummy payment and cart clear

## Dummy Payment Flow

1. User logs in
2. User adds products to cart
3. User opens cart and goes to checkout
4. User clicks **Pay Now**
5. App clears cart and shows **Payment Successful**

## Notes

- This is a learning/demo project and does not use a real payment gateway.
- For production, add stronger validation, CSRF protection, secure cookies, and proper error handling.
