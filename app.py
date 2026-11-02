import os
import io
import base64
from datetime import date
from functools import wraps

import numpy as np
import pandas as pd
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template, flash, redirect, url_for
from werkzeug.utils import secure_filename
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-secret")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {"csv"}

REQUIRED_COLUMNS = ["observation_date", "location", "temperature", "humidity", "rainfall"]

def db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "weather_analysis"),
        connection_timeout=10,
    )

def initialize_database():
    conn = db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS weather_records (
            record_id BIGINT AUTO_INCREMENT PRIMARY KEY,
            observation_date DATE NOT NULL,
            location VARCHAR(120) NOT NULL,
            temperature DOUBLE NOT NULL COMMENT 'Degrees Celsius',
            humidity DOUBLE NOT NULL COMMENT 'Percent, 0 to 100',
            rainfall DOUBLE NOT NULL COMMENT 'Millimetres, >= 0',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_weather_date_location (observation_date, location),
            INDEX idx_weather_date (observation_date),
            INDEX idx_weather_location (location)
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def fetch_records(location=None, start_date=None, end_date=None, limit=5000):
    conn = db_connection()
    cur = conn.cursor(dictionary=True)
    sql = """SELECT record_id, observation_date, location, temperature, humidity, rainfall
             FROM weather_records WHERE 1=1"""
    params = []
    if location:
        sql += " AND location LIKE %s"
        params.append(f"%{location}%")
    if start_date:
        sql += " AND observation_date >= %s"
        params.append(start_date)
    if end_date:
        sql += " AND observation_date <= %s"
        params.append(end_date)
    sql += " ORDER BY observation_date DESC, location ASC LIMIT %s"
    params.append(int(limit))
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def dataframe_from_db(location=None):
    rows = fetch_records(location=location, limit=10000)
    if not rows:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    df = pd.DataFrame(rows)
    df["observation_date"] = pd.to_datetime(df["observation_date"])
    return df

def summary_payload(df):
    if df.empty:
        return {"records": 0, "temperature": None, "humidity": None, "rainfall": None}
    return {
        "records": int(len(df)),
        "temperature": {
            "min": round(float(df["temperature"].min()), 2),
            "max": round(float(df["temperature"].max()), 2),
            "average": round(float(df["temperature"].mean()), 2),
        },
        "humidity": {
            "min": round(float(df["humidity"].min()), 2),
            "max": round(float(df["humidity"].max()), 2),
            "average": round(float(df["humidity"].mean()), 2),
        },
        "rainfall": {
            "min": round(float(df["rainfall"].min()), 2),
            "max": round(float(df["rainfall"].max()), 2),
            "average": round(float(df["rainfall"].mean()), 2),
            "total": round(float(df["rainfall"].sum()), 2),
        },
    }

def monthly_summary(df):
    if df.empty:
        return []
    work = df.copy()
    work["month"] = work["observation_date"].dt.to_period("M").astype(str)
    grouped = work.groupby("month").agg(
        temperature_min=("temperature", "min"),
        temperature_max=("temperature", "max"),
        temperature_average=("temperature", "mean"),
        humidity_average=("humidity", "mean"),
        rainfall_total=("rainfall", "sum"),
        rainfall_average=("rainfall", "mean"),
    ).reset_index()
    numeric = grouped.select_dtypes(include="number").columns
    grouped[numeric] = grouped[numeric].round(2)
    return grouped.to_dict(orient="records")

def make_chart(df, kind):
    fig, ax = plt.subplots(figsize=(9, 4.5))
    if df.empty:
        ax.text(0.5, 0.5, "No weather records yet", ha="center", va="center")
        ax.set_axis_off()
    else:
        work = df.copy()
        work["month"] = work["observation_date"].dt.to_period("M").astype(str)
        grouped = work.groupby("month").agg(
            temperature=("temperature", "mean"),
            rainfall=("rainfall", "sum")
        ).reset_index()
        if kind == "temperature":
            ax.plot(grouped["month"], grouped["temperature"], marker="o", linewidth=2)
            ax.set_title("Monthly Average Temperature")
            ax.set_ylabel("Temperature (°C)")
        else:
            ax.bar(grouped["month"], grouped["rainfall"])
            ax.set_title("Monthly Total Rainfall")
            ax.set_ylabel("Rainfall (mm)")
        ax.set_xlabel("Month")
        ax.tick_params(axis="x", rotation=35)
        ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    output = io.BytesIO()
    fig.savefig(output, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    output.seek(0)
    return base64.b64encode(output.read()).decode("ascii")

@app.route("/")
def home():
    try:
        df = dataframe_from_db()
        stats = summary_payload(df)
        months = monthly_summary(df)
        recent = fetch_records(limit=12)
        temp_chart = make_chart(df, "temperature")
        rain_chart = make_chart(df, "rainfall")
        return render_template("index.html", stats=stats, months=months, recent=recent,
                               temp_chart=temp_chart, rain_chart=rain_chart)
    except Error as exc:
        return render_template("error.html", message=f"Database connection failed: {exc}"), 503

@app.route("/upload", methods=["POST"])
def upload_csv():
    file = request.files.get("file")
    if not file or not file.filename:
        flash("Choose a CSV file first.", "error")
        return redirect(url_for("home"))
    if not allowed_file(file.filename):
        flash("Only CSV files are accepted.", "error")
        return redirect(url_for("home"))
    try:
        df = pd.read_csv(file)
        df.columns = [str(c).strip().lower() for c in df.columns]
        missing_columns = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing_columns:
            flash("CSV is missing required columns: " + ", ".join(missing_columns), "error")
            return redirect(url_for("home"))

        quality = {"total_rows": int(len(df)), "missing_rows": 0, "invalid_rows": 0,
                   "duplicate_rows": 0, "inserted_rows": 0}
        work = df[REQUIRED_COLUMNS].copy()
        work["observation_date"] = pd.to_datetime(work["observation_date"], errors="coerce")
        work["location"] = work["location"].astype("string").str.strip()
        for col in ["temperature", "humidity", "rainfall"]:
            work[col] = pd.to_numeric(work[col], errors="coerce")

        missing_mask = work.isna().any(axis=1) | work["location"].eq("")
        quality["missing_rows"] = int(missing_mask.sum())
        work = work.loc[~missing_mask].copy()

        valid_mask = (
            work["humidity"].between(0, 100)
            & work["rainfall"].ge(0)
            & work["temperature"].between(-100, 70)
        )
        quality["invalid_rows"] = int((~valid_mask).sum())
        work = work.loc[valid_mask].copy()
        work["observation_date"] = work["observation_date"].dt.date
        work = work.drop_duplicates(subset=["observation_date", "location"], keep="first")
        quality["duplicate_rows"] += int(len(df) - quality["missing_rows"] - quality["invalid_rows"] - len(work))

        conn = db_connection()
        cur = conn.cursor()
        sql = """INSERT IGNORE INTO weather_records
                 (observation_date, location, temperature, humidity, rainfall)
                 VALUES (%s, %s, %s, %s, %s)"""
        values = [
            (r.observation_date, str(r.location), float(r.temperature), float(r.humidity), float(r.rainfall))
            for r in work.itertuples(index=False)
        ]
        if values:
            cur.executemany(sql, values)
            quality["inserted_rows"] = int(cur.rowcount)
        quality["duplicate_rows"] += max(0, len(values) - quality["inserted_rows"])
        conn.commit()
        cur.close()
        conn.close()
        flash(
            f"Upload complete: {quality['inserted_rows']} inserted, "
            f"{quality['missing_rows']} missing, {quality['invalid_rows']} invalid, "
            f"{quality['duplicate_rows']} duplicate rows.",
            "success"
        )
        return redirect(url_for("home"))
    except (pd.errors.ParserError, UnicodeDecodeError, ValueError) as exc:
        flash(f"Could not read or validate the CSV: {exc}", "error")
        return redirect(url_for("home"))
    except Error as exc:
        flash(f"MySQL error: {exc}", "error")
        return redirect(url_for("home"))
    except Exception as exc:
        app.logger.exception("CSV upload failed")
        flash(f"Upload failed: {exc}", "error")
        return redirect(url_for("home"))

@app.route("/api/records")
def api_records():
    try:
        rows = fetch_records(
            location=request.args.get("location"),
            start_date=request.args.get("start_date"),
            end_date=request.args.get("end_date"),
            limit=min(int(request.args.get("limit", 500)), 5000),
        )
        return jsonify(rows)
    except (ValueError, Error) as exc:
        return jsonify({"error": str(exc)}), 400

@app.route("/api/summary")
def api_summary():
    try:
        df = dataframe_from_db(request.args.get("location"))
        return jsonify(summary_payload(df))
    except Error as exc:
        return jsonify({"error": str(exc)}), 503

@app.route("/api/monthly")
def api_monthly():
    try:
        df = dataframe_from_db(request.args.get("location"))
        return jsonify(monthly_summary(df))
    except Error as exc:
        return jsonify({"error": str(exc)}), 503

@app.route("/api/records/<int:record_id>", methods=["DELETE"])
def api_delete_record(record_id):
    try:
        conn = db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM weather_records WHERE record_id = %s", (record_id,))
        deleted = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        if not deleted:
            return jsonify({"error": "Record not found"}), 404
        return jsonify({"message": "Record deleted", "record_id": record_id})
    except Error as exc:
        return jsonify({"error": str(exc)}), 503

@app.route("/health")
def health():
    try:
        conn = db_connection()
        conn.ping(reconnect=True, attempts=1, delay=0)
        conn.close()
        return jsonify({"status": "ok", "database": "connected"})
    except Error as exc:
        return jsonify({"status": "error", "database": str(exc)}), 503

if __name__ == "__main__":
    try:
        initialize_database()
    except Error as exc:
        print(f"Could not initialize MySQL: {exc}")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
