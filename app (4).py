from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import sqlite3
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_key_change_in_prod")
CORS(app)

DB_PATH = os.path.join(os.path.dirname(__file__), "crm.db")


# ── DATABASE ──────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id          INTEGER  PRIMARY KEY AUTOINCREMENT,
                name        TEXT     NOT NULL,
                email       TEXT     NOT NULL UNIQUE,
                phone       TEXT     DEFAULT '',
                company     TEXT     DEFAULT '',
                source      TEXT     DEFAULT 'website'
                                CHECK(source IN ('website','referral','social','other')),
                status      TEXT     NOT NULL DEFAULT 'new'
                                CHECK(status IN ('new','contacted','qualified','converted','lost')),
                notes       TEXT     DEFAULT '',
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS leads_updated_at
            AFTER UPDATE ON leads
            BEGIN
                UPDATE leads SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END
        """)
        conn.commit()


def row_to_dict(row):
    return dict(row)


# ── HELPERS ───────────────────────────────────────────────────────────────────
VALID_STATUSES = ("new", "contacted", "qualified", "converted", "lost")
VALID_SOURCES  = ("website", "referral", "social", "other")


# ── API ROUTES ────────────────────────────────────────────────────────────────

@app.route("/api/leads", methods=["GET"])
def list_leads():
    status = request.args.get("status", "").strip()
    source = request.args.get("source", "").strip()
    q      = request.args.get("q", "").strip()
    sort   = request.args.get("sort", "created_at").strip()
    order  = request.args.get("order", "desc").strip().upper()

    allowed_sorts = {"created_at", "updated_at", "name", "status"}
    if sort not in allowed_sorts:
        sort = "created_at"
    if order not in ("ASC", "DESC"):
        order = "DESC"

    sql, params = "SELECT * FROM leads WHERE 1=1", []

    if status and status != "all":
        sql += " AND status = ?"
        params.append(status)

    if source and source != "all":
        sql += " AND source = ?"
        params.append(source)

    if q:
        sql += " AND (name LIKE ? OR email LIKE ? OR phone LIKE ? OR company LIKE ?)"
        like = f"%{q}%"
        params += [like, like, like, like]

    sql += f" ORDER BY {sort} {order}"

    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()

    return jsonify([row_to_dict(r) for r in rows])


@app.route("/api/leads", methods=["POST"])
def create_lead():
    data    = request.get_json(force=True)
    name    = (data.get("name")    or "").strip()
    email   = (data.get("email")   or "").strip()
    phone   = (data.get("phone")   or "").strip()
    company = (data.get("company") or "").strip()
    source  = (data.get("source")  or "website").strip()
    status  = (data.get("status")  or "new").strip()
    notes   = (data.get("notes")   or "").strip()

    if not name:
        return jsonify({"error": "Name is required"}), 400
    if not email or "@" not in email:
        return jsonify({"error": "Valid email is required"}), 400
    if status not in VALID_STATUSES:
        status = "new"
    if source not in VALID_SOURCES:
        source = "website"

    try:
        with get_db() as conn:
            cur = conn.execute(
                "INSERT INTO leads (name, email, phone, company, source, status, notes) VALUES (?,?,?,?,?,?,?)",
                (name, email, phone, company, source, status, notes),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM leads WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
        return jsonify(row_to_dict(row)), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "Email already exists"}), 409


@app.route("/api/leads/<int:lid>", methods=["GET"])
def get_lead(lid):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lid,)).fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row_to_dict(row))


@app.route("/api/leads/<int:lid>", methods=["PUT"])
def update_lead(lid):
    with get_db() as conn:
        existing = conn.execute("SELECT * FROM leads WHERE id = ?", (lid,)).fetchone()
        if not existing:
            return jsonify({"error": "Not found"}), 404

        data    = request.get_json(force=True)
        name    = (data.get("name")    or existing["name"]).strip()
        email   = (data.get("email")   or existing["email"]).strip()
        phone   = data.get("phone",   existing["phone"])
        company = data.get("company", existing["company"])
        source  = (data.get("source")  or existing["source"]).strip()
        status  = (data.get("status")  or existing["status"]).strip()
        notes   = data.get("notes",   existing["notes"])

        if not name:
            return jsonify({"error": "Name is required"}), 400
        if "@" not in email:
            return jsonify({"error": "Valid email is required"}), 400
        if status not in VALID_STATUSES:
            return jsonify({"error": "Invalid status"}), 400
        if source not in VALID_SOURCES:
            return jsonify({"error": "Invalid source"}), 400

        try:
            conn.execute(
                "UPDATE leads SET name=?, email=?, phone=?, company=?, source=?, status=?, notes=? WHERE id=?",
                (name, email, phone, company, source, status, notes, lid),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM leads WHERE id = ?", (lid,)).fetchone()
        except sqlite3.IntegrityError:
            return jsonify({"error": "Email already exists"}), 409

    return jsonify(row_to_dict(row))


@app.route("/api/leads/<int:lid>", methods=["DELETE"])
def delete_lead(lid):
    with get_db() as conn:
        row = conn.execute("SELECT id FROM leads WHERE id = ?", (lid,)).fetchone()
        if not row:
            return jsonify({"error": "Not found"}), 404
        conn.execute("DELETE FROM leads WHERE id = ?", (lid,))
        conn.commit()
    return jsonify({"deleted": lid})


@app.route("/api/stats", methods=["GET"])
def stats():
    with get_db() as conn:
        total     = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        new_l     = conn.execute("SELECT COUNT(*) FROM leads WHERE status='new'").fetchone()[0]
        contacted = conn.execute("SELECT COUNT(*) FROM leads WHERE status='contacted'").fetchone()[0]
        qualified = conn.execute("SELECT COUNT(*) FROM leads WHERE status='qualified'").fetchone()[0]
        converted = conn.execute("SELECT COUNT(*) FROM leads WHERE status='converted'").fetchone()[0]
        lost      = conn.execute("SELECT COUNT(*) FROM leads WHERE status='lost'").fetchone()[0]

        # source breakdown
        sources = conn.execute(
            "SELECT source, COUNT(*) as count FROM leads GROUP BY source"
        ).fetchall()

    return jsonify({
        "total":     total,
        "new":       new_l,
        "contacted": contacted,
        "qualified": qualified,
        "converted": converted,
        "lost":      lost,
        "sources":   [row_to_dict(r) for r in sources],
    })


# ── FRONTEND ──────────────────────────────────────────────────────────────────
@app.route("/")
def home():
    return render_template("index.html")


# ── ENTRY POINT ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
