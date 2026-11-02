# Weather Data Analysis System

A Flask + MySQL web application for analysing **recorded** weather observations. It does not forecast weather.

## Features
- CSV upload and validation for date, location, temperature, humidity and rainfall.
- Transparent counts for missing, invalid and duplicate rows.
- MySQL persistence with a unique date/location constraint.
- Daily records and monthly min/max/average summaries.
- Monthly average temperature trend and monthly rainfall total charts.
- JSON REST APIs, record search/filter and delete.
- Responsive browser dashboard.

## Units and validation
- Temperature: degrees Celsius (°C), accepted range -100 to 70.
- Humidity: percent (%), accepted range 0 to 100.
- Rainfall: millimetres (mm), must be zero or greater.
- One record per observation date and location. Repeated date/location pairs are treated as duplicates.
- Required CSV headers: `observation_date,location,temperature,humidity,rainfall`.
- Dates should be parseable by Pandas (recommended format `YYYY-MM-DD`).

## Run locally (Windows)
1. Install Python 3.12 or newer and MySQL Server (or MySQL Community Server).
2. Create a database and table by running `schema.sql` in MySQL Workbench.
3. Open this project folder in Command Prompt.
4. Create and activate a virtual environment:
   ```bat
   py -3.12 -m venv venv
   venv\Scripts\activate
   ```
5. Install packages:
   ```bat
   pip install -r requirements.txt
   ```
6. Copy `.env.example` to `.env` and enter your MySQL host, port, database, username and password.
7. Start the website:
   ```bat
   python app.py
   ```
8. Open `http://127.0.0.1:5000` in your browser.
9. Upload `sample_weather.csv` to test the application.

If your computer has a different Python launcher command, use `python -m venv venv` instead of step 4's first line.

## REST API
- `GET /health` — app/database health.
- `GET /api/records` — records. Optional query parameters: `location`, `start_date`, `end_date`, `limit`.
- `GET /api/summary` — descriptive statistics.
- `GET /api/monthly` — monthly grouped summary.
- `DELETE /api/records/<record_id>` — delete one record.

## Deployment
This app can be deployed to Render as a Python Web Service, but **Render does not provide a built-in managed MySQL database**. Create/use an external MySQL service first, then copy its connection values into Render Environment Variables:
`SECRET_KEY`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`.

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Health check path: `/health`

Keep `.env` out of GitHub. Never commit database passwords. Confirm that your MySQL provider allows connections from your deployed app and uses TLS if required by that provider. The database should be reachable before testing `/health`.

## Project structure
```text
Weather_Data_Analysis_System/
├── app.py
├── requirements.txt
├── schema.sql
├── sample_weather.csv
├── .env.example
├── README.md
├── templates/
│   ├── index.html
│   └── error.html
└── static/
    └── style.css
```
