import os
import re

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user = session["user_id"]
    balance = db.execute("SELECT cash FROM users WHERE id = ?", user)
    transactions = db.execute("SELECT symbol, SUM(shares) AS total_shares, price FROM transactions WHERE userid = ? GROUP BY symbol HAVING SUM(shares) > 0 ORDER BY symbol", user)
    investment = 0
    data = []

    #Basic API plan is 5 requests per second, so it might be slow, query name and current price

    for row in transactions:
        loop = lookup(row["symbol"])
        row["name"] = loop["name"]
        row["price"] = loop["price"]
        row["total"] = loop["price"] * row["total_shares"]
        investment += row["total"]
        data.append(loop)

    total = balance[0]["cash"] + investment
    zipped = zip(transactions, data)

    return render_template("index.html", zipped = zipped, balance = balance[0]["cash"], investment = investment, total = total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    user = session["user_id"]
    balance = db.execute("SELECT cash FROM users WHERE id = ?", user)

    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")

        if not symbol:
            return apology("insert a symbol")

        if not request.form.get("shares"):
            return apology("insert a number of shares")

        if lookup(symbol) != None:
            quote = lookup(symbol)

            if not request.form.get("shares").lstrip("-").isdigit():
                return apology("insert an integer")

            shares = int(request.form.get("shares"))

            if shares >= 1: #filter characters and fractionals
                if (shares * quote["price"]) <= balance[0]["cash"]: #balance without that [0] returns a list: "cash", "10000"
                    db.execute("INSERT INTO transactions (userid, symbol, shares, price) VALUES (?, ?, ?, ?)", user, quote["symbol"], shares, quote["price"])
                    #Deduct from user balance
                    deduction = shares * quote["price"]
                    db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", deduction, user)
                    return redirect("/")

                else:
                    return apology("need more funds", 400)

            else:
                return apology("insert a positive number of shares", 400)

        else:
            return apology("symbol does not exist", 400)

    else:
        return render_template("buy.html", balance = balance[0]["cash"])


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user = session["user_id"]
    transactions = db.execute("SELECT * FROM transactions WHERE userid = ? order BY time DESC", user)
    return render_template("history.html", transactions = transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Ensure username was submitted
        if not username:
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not password:
            return apology("must provide password", 400)

        elif re.search("[';]", password):
            return apology("generic error: password", 400)

        elif re.search("[';]", username):
            return apology("generic error: username", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], password):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("insert a symbol", 400)

        # Check if symbol exists
        symbol = request.form.get("symbol")

        if lookup(symbol) != None:
            quote = lookup(symbol)
            return render_template("quoted.html", name = quote["name"], qsymbol = quote["symbol"], price = quote["price"])

        else:
            return apology("symbol does not exist")

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    session.clear()
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        if not username:
            return apology("must provide username", 400)

        elif not password:
            return apology("must provide password", 400)

        elif not confirmation:
            return apology("must re-enter password", 400)

        elif re.search("[';]", username):
            return apology("generic error: username", 400)

        elif re.search("[';]", password):
            return apology("generic error: password", 400)

        elif len(password) < 8:
            return apology("password needs special characters and a minimum of 8 characters")

        elif not re.search("[!@#$%^&*]", password):
            return apology("password needs special characters and a minimum of 8 characters")

        if password == confirmation:
            #Check if usename exists
            rows = db.execute("SELECT * FROM users WHERE username = ?", username)
            if len(rows) == 1:
                return apology("Username already exists.", 400)

            #Hash password
            hash = generate_password_hash(password)

            #Insert new user
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash)
        else:
            return apology("Confirmation password is incorrect", 400)

        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    user = session["user_id"]
    balance = db.execute("SELECT cash FROM users WHERE id = ?", user)
    transactions = db.execute("SELECT symbol, shares, price FROM transactions WHERE userid = ? GROUP BY symbol ORDER BY symbol", user)

    """Sell shares of stock"""
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("insert a symbol", 400)

        if not request.form.get("shares"):
            return apology("insert number of shares", 400)

        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))

        if symbol != None:
            if shares >= 1:
                share = db.execute("SELECT shares FROM transactions WHERE symbol = ? AND userid = ?", symbol, user)
                if shares <= share[0]["shares"]:
                    quote = lookup(symbol)
                    sold = shares * float(quote["price"])

                    #Add to user balance
                    db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", sold, user)

                    #Deduct shares
                    db.execute("INSERT INTO transactions (userid, symbol, shares, price) VALUES (?, ?, ? * -1, ?)", user, symbol, shares, sold)

                    return redirect("/")

                else:
                    return apology("need more shares", 400)

            else:
                return apology("insert a positive number", 400)

        else:
            return apology("symbol not found")

    else:
        return render_template("sell.html", symbols = transactions, balance = balance[0]["cash"])
