from flask import Flask, render_template, request, redirect, session, url_for
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
import yfinance as yf
import pandas as pd

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# MySQL Connection
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '***********'#Your Sql Pwd
app.config['MYSQL_DB'] = 'stock_demo'

mysql = MySQL(app)

# ------------- LOGIN & SIGNUP ----------------
@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cursor.fetchone()
        cursor.close()
        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            return redirect(url_for('dashboard'))
        else:
            return "Invalid credentials"
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        cursor = mysql.connection.cursor()
        cursor.execute("INSERT INTO users(username, password) VALUES(%s, %s)", (username, password))
        mysql.connection.commit()
        cursor.close()
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ---------------- DASHBOARD -----------------
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    message = None
    if request.method == 'POST':
        symbol = request.form['symbol'].upper()
        quantity = int(request.form['quantity'])
        action = request.form.get('action')
        if not action:
            message = "Please select Buy or Sell."
        else:
            action = action.upper()
            stock = yf.Ticker(symbol)
            data = stock.history(period='1d')
            price = float(data['Close'].iloc[0])

            # Save transaction
            cursor = mysql.connection.cursor()
            cursor.execute(
                "INSERT INTO transactions(user_id, stock_symbol, quantity, price, type) VALUES(%s,%s,%s,%s,%s)",
                (session['user_id'], symbol, quantity, price, action)
            )
            mysql.connection.commit()
            cursor.close()

            message = f"{action} {quantity} shares of {symbol} at ${price:.2f}"

    # Portfolio Calculation
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT stock_symbol, type, SUM(quantity), AVG(price) FROM transactions WHERE user_id=%s GROUP BY stock_symbol, type", (session['user_id'],))
    data = cursor.fetchall()
    cursor.close()

    portfolio = {}
    for row in data:
        symbol, typ, qty, avg_price = row
        qty = float(qty)
        avg_price = float(avg_price)
        if symbol not in portfolio:
            portfolio[symbol] = {'buy':0, 'sell':0, 'avg_buy':0}
        if typ == 'BUY':
            portfolio[symbol]['buy'] += qty
            portfolio[symbol]['avg_buy'] = avg_price
        else:
            portfolio[symbol]['sell'] += qty

    # Calculate current price & profit/loss
    for sym in portfolio:
        current_price = float(yf.Ticker(sym).history(period='1d')['Close'].iloc[0])
        portfolio[sym]['current_price'] = current_price
        net_qty = portfolio[sym]['buy'] - portfolio[sym]['sell']
        portfolio[sym]['net_qty'] = net_qty
        buy_price = portfolio[sym]['avg_buy']
        quantity = net_qty
        portfolio[sym]['profit_loss'] = (current_price - buy_price) * quantity

    # ---------------- Fetch All Transactions ----------------
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT stock_symbol, type, quantity, price, date
        FROM transactions
        WHERE user_id=%s
        ORDER BY date DESC
    """, (session['user_id'],))
    transactions = cursor.fetchall()
    cursor.close()

    # ---------------- Render Template ----------------
    return render_template(
        'dashboard.html',
        username=session['username'],
        portfolio=portfolio,
        transactions=transactions,
        message=message
    )



if __name__ == '__main__':
    app.run(debug=True)

