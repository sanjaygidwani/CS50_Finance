from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    
    # factor out all the entries of user from portfolio
    result = db.execute("SELECT * from portfolio WHERE id=:id", id=session["user_id"])
    
    # factor out total price of all shares
    cost = db.execute("SELECT sum(total) from portfolio WHERE id=:id", id=session["user_id"])
    
    # newly registered user
    if cost[0]["sum(total)"] == None:
        remain = 10000
    else:
        # remaining money in the account
        remain = 10000 - float(cost[0]["sum(total)"]) 
    
    return render_template("index.html", query=result, cash=usd(remain), total=usd(10000.00))
    
@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    
    if request.method == "GET":
        return render_template("buy.html")
        
    else:
        # ensure symbol was provided
        if not request.form.get("symbol") :
            return apology("You must provide symbol")
        
        # ensure shares were provided
        if not request.form.get("shares") :
            return apology("You must provide shares")
    
        # store symbol in a variable
        symbol = (request.form.get("symbol")).upper()
    
        # lookup for name, symbol, price and store it in a variable
        quote = lookup(symbol)
        
        # ensure symbol was valid
        if type(quote) != dict :
            return apology("Invalid symbol")
    
        # ensure shares were valid
        if int(request.form.get("shares")) <= 0 :
            return apology("Invalid shares")
    
        # factor out user's entries
        query = db.execute("SELECT * FROM users WHERE id = :ID", ID=session["user_id"])
    
        # ensure sufficient cash is available
        if query[0]["cash"] < int(request.form.get("shares")) * quote["price"] :
            return apology("Insufficient cash")
    
        # number of shares times cost
        purchase = int(request.form.get("shares")) * quote["price"]
    
        # update entries in transactions
        db.execute("INSERT INTO transactions(id, symbol, name, shares, price) VALUES(:id, :symbol, :name, :shares, :price)",
        id=session["user_id"], symbol=symbol, name=quote["name"], shares=int(request.form.get("shares")), price=usd(quote["price"]))
    
        # update user's cash in users
        db.execute("UPDATE users SET cash=cash - :purchase WHERE id = :id", purchase=usd(purchase), id=session["user_id"])
    
        # factor out user's shares of entered symbol
        stock = db.execute("SELECT shares FROM portfolio WHERE id = :id AND symbol=:symbol", id=session["user_id"], symbol=symbol)
                           
        # ensure user has shares of entered symbol
        if not stock:
            db.execute("INSERT INTO portfolio (id, symbol, name, shares, price, total) VALUES(:id, :symbol, :name, :shares, :price, :total)",
            id=session["user_id"], symbol=symbol, name=quote["name"], shares=int(request.form.get("shares")), price=usd(quote["price"]),
            total=usd(purchase))
                        
        # else update shares, price and total
        else:
            value = stock[0]["shares"] + int(request.form.get("shares"))
            db.execute("UPDATE portfolio SET shares=:shares WHERE id=:id AND symbol=:symbol", shares=value, id=session["user_id"],
            symbol=symbol)
            db.execute("UPDATE portfolio SET total=:total WHERE id=:id AND symbol=:symbol", total=usd(value * quote["price"]), id=session["user_id"],
            symbol=symbol)
        
        return redirect(url_for("index"))

@app.route("/history")
@login_required
def history():
    
    # factor out all the entries of user from transactions
    history = db.execute("SELECT * from transactions WHERE id=:id", id=session["user_id"])
    
    return render_template("history.html", history=history)

@app.route("/login", methods=["GET", "POST"])
def login():
    
    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("You must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("You must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("Invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    
    # display quote web-page
    return render_template("quote.html")
        
@app.route("/quoted", methods=["GET", "POST"])
@login_required
def quoted():
    
    # ensure symbol was provided
    if not request.form.get("symbol") :
        return apology("You must provide symbol")
    
    # store symbol in a variable
    symbol = request.form.get("symbol")
    
    # lookup for name, symbol, price and store it in a variable
    quote = lookup(symbol)
    
    # ensure symbol was valid
    if type(quote) == dict :
        return render_template("quoted.html", name = quote["name"], symbol = quote["symbol"], price = str(usd(quote["price"])))
    else:
        return apology("Invalid symbol")
    
@app.route("/register", methods=["GET", "POST"])
def register():
    
    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("You must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("You must provide password")
        
        # ensure password was submitted again
        elif not request.form.get("confirm-password"):
            return apology("You must provide password again")
        
        # ensure passwords matched
        elif request.form.get("password") != request.form.get("confirm-password"):
            return apology("Your passwords didn't matched")
        
        # ensure username was valid
        variable=str(request.form.get("username"))
        if variable[0].isdigit() :
            return apology("Invalid username")

        # hash password for security
        hashe = pwd_context.hash(request.form.get("password"))
        
        # insert username and password into users table
        result = db.execute("INSERT INTO users(username, hash) VALUES(:username, :hash)", username=request.form.get("username"), hash=hashe)
        
        # ensure username does not already exists
        if not result:
            return apology("Username already exists")
            
        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
        
        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    
    if request.method == "GET":
        return render_template("sell.html")
        
    else:
        # ensure symbol was provided
        if not request.form.get("symbol") :
            return apology("You must provide symbol")
        
        # ensure shares were provided
        if not request.form.get("shares") :
            return apology("You must provide shares")
    
        # store symbol in a variable
        symbol = (request.form.get("symbol")).upper()
    
        # lookup for name, symbol, price and store it in a variable
        quote = lookup(symbol)
        
        # ensure symbol was valid
        if type(quote) != dict :
            return apology("Invalid symbol")
    
        # ensure shares were valid
        if int(request.form.get("shares")) <= 0 :
            return apology("Invalid shares")
        
        # factor out required shares from users
        shares = db.execute("SELECT shares FROM portfolio WHERE id=:id AND symbol=:symbol", id=session["user_id"], symbol=symbol)
        
        # ensure sufficient shares are available
        if not shares or int(shares[0]["shares"]) < int(request.form.get("shares")) :
            return apology("Insufficient shares")
            
        purchase = int(request.form.get("shares")) * quote["price"]
        
        # updating transaction history in transactions
        db.execute("INSERT INTO transactions(id, symbol, name, shares, price) VALUES(:id, :symbol, :name, :shares, :price)",
        id=session["user_id"], symbol=symbol, name=quote["name"], shares= - int(request.form.get("shares")), price=usd(quote["price"]))
                       
        # update user's cash in users
        db.execute("UPDATE users SET cash=cash + :purchase WHERE id = :id", purchase=usd(purchase), id=session["user_id"])
                        
        # reduce number of shares
        reduced = int(shares[0]["shares"]) - int(request.form.get("shares"))
        
        # delete row from portfolio if reduced is zero
        if reduced == 0:
            db.execute("DELETE FROM portfolio WHERE id=:id AND symbol=:symbol", id=session["user_id"], symbol=symbol)
            
        # update shares
        else:
            db.execute("UPDATE portfolio SET shares=:shares WHERE id=:id AND symbol=:symbol", shares=reduced, id=session["user_id"],
            symbol=symbol)
            db.execute("UPDATE portfolio SET total=:total WHERE id=:id AND symbol=:symbol", total=usd(reduced * quote["price"]), id=session["user_id"],
            symbol=symbol)
        
        return redirect(url_for("index"))

@app.route("/password", methods=["GET", "POST"])
@login_required
def password():
    
    if request.method == "GET":
        return render_template("password.html")
        
    else:
        # ensure old password was submitted
        if not request.form.get("old-password"):
            return apology("You must provide old password")

        # ensure new password was submitted
        elif not request.form.get("new-password"):
            return apology("You must provide new password")
        
        # ensure new password was submitted again
        elif not request.form.get("new-password-again"):
            return apology("You must provide new password again")
            
        # query database for password
        rows = db.execute("SELECT hash FROM users WHERE id = :id", id=session["user_id"])

        # ensure password was correct
        if not pwd_context.verify(request.form.get("old-password"), rows[0]["hash"]):
            return apology("Invalid old password")
        
        # ensure passwords matched
        elif request.form.get("new-password") != request.form.get("new-password-again"):
            return apology("Your new passwords didn't matched")
            
        # hash password for security
        hashe = pwd_context.hash(request.form.get("new-password"))
        
        # update new password into users table
        db.execute("UPDATE users SET hash=:hash WHERE id=:id", hash=hashe, id=session["user_id"])
        
        return redirect(url_for("login"))
