from functools import wraps
from flask import Flask, jsonify, request
import jwt

app = Flask(__name__)

SECRET_KEY = "when_you_see_it"

BOOKS = [
    {"id": 1, "title": "Book 1", "author": "Author 1", "price": 10000},
    {"id": 2, "title": "Book 2", "author": "Author 2", "price": 20000},
    {"id": 3, "title": "Book 3", "author": "Author 3", "price": 30000},
    {"id": 4, "title": "Book 4", "author": "Author 4", "price": 40000},
    {"id": 5, "title": "Book 5", "author": "Author 5", "price": 50000},
    {"id": 6, "title": "Book 6", "author": "Author 6", "price": 60000},
    {"id": 7, "title": "Book 7", "author": "Author 7", "price": 70000},
]

def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth_header = request.headers.get("Authorization")

            if not auth_header or not auth_header.startswith("Bearer "):
                return (
                    jsonify(
                        {
                            "statusCode": 401,
                            "message": "Missing Bearer token",
                        }
                    ),
                    401,
                )

            token = auth_header.split(" ")[1]

            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            except jwt.ExpiredSignatureError:
                return (
                    jsonify(
                        {
                            "statusCode": 401,
                            "message": "Token has expired",
                        }
                    ), 401
                )
            except jwt.InvalidTokenError:
                return (
                    jsonify({
                        "statusCode": 401, 
                        "message": "Invalid token"
                        }), 401
                )

            user_role = payload.get("role")
            if user_role not in allowed_roles:
                return (
                    jsonify(
                        {
                            "statusCode": 403,
                            "message": f"Role '{user_role}' is not allowed to perform this action.",
                        }
                    ),
                    403,
                )

            return f(*args, **kwargs)

        return decorated

    return decorator

@app.route("/login/viewer", methods=["POST"])
def login_viewer():
    token = jwt.encode(
        {"user": "user_viewer", "role": "viewer"},
        SECRET_KEY,
        algorithm="HS256",
    )
    return jsonify({"access_token": token, "role": "viewer"})

@app.route("/login/admin", methods=["POST"])
def login_admin():
    token = jwt.encode(
        {"user": "user_admin", "role": "admin"},
        SECRET_KEY,
        algorithm="HS256",
    )
    return jsonify({"access_token": token, "role": "admin"})

@app.patch("/books/<int:bid>")
@role_required("admin")
def patchBook(bid):
    i = next((k for k,b in enumerate(BOOKS) if b["id"] == bid), None)
    if i is None:
        return jsonify({
            "statusCode": 404,
            "message": "Not found"
        }), 404

    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({
            "statusCode": 400,
            "message": "Missing body"
        }), 400

    if "price" in data and data["price"] < 0:
        return jsonify({
            "statusCode": 422,
            "message": "Price must be larger than 0"
        }), 422

    for k in "title author price".split():
        if k in data:
            BOOKS[i][k] = data[k]

    return jsonify(BOOKS[i]), 200

@app.delete("/books/<int:bid>")
@role_required("admin")
def deleteBook(bid):
    i = next((k for k,b in enumerate(BOOKS) if b["id"] == bid), None)
    if i is None:
        return jsonify({
            "statusCode": 404,
            "message": "Not found"
        }), 404

    BOOKS.pop(i)

    return "", 204

if (__name__ == "__main__"):
    app.run(host="127.0.0.1", port=5000, debug=True)