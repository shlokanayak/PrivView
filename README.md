# PrivView

## Honours - Cyber Security & Forensics | Cyber Forensics & Laws | Lab CA Mini Project | Semester V | TY Computer Engineering (2026-27)

**Team Members:**
- Shloka Nayak - 16010124202
- N Pavithra - 16010124182

PrivView is a web application for sharing sensitive datasets in a safer way. It is made for data like medical and financial records, where external analysts need to analyse the data but should not see real values or personal details.

An admin uploads a CSV or Excel file. The system cleans it, hides the sensitive numbers, encrypts it and stores it. The admin then chooses which analysts can use it. Analysts can only see charts, tables and a PDF report. They never get the raw rows.

## What it does

**Admin**
- Logs in with password and email OTP
- Uploads a CSV or XLSX file and watches the 7 processing steps live
- Previews the first 10 protected rows and downloads the protected CSV
- Gives or removes dataset access for each analyst
- Changes user roles and active status
- Reads the activity log (latest 300 events, with a failures only filter)
- Deletes datasets

**Analyst**
- Logs in with password and email OTP
- Sees only the datasets the admin has shared
- Opens a workspace with filters (measure, compare by, date range)
- Views 4 charts (trend, group difference, histogram, correlation), a group table and a summary table
- Downloads a PDF report of the current view

## Tech stack

| Part | Used |
|---|---|
| Frontend | React 18, Vite, React Router, Recharts |
| Backend | Python, Flask, Flask-SQLAlchemy |
| Database | PostgreSQL |
| Email OTP | Gmail SMTP |
| Encryption | AES-256-GCM (cryptography library) |
| Files and reports | openpyxl, ReportLab |

## Security features

| Feature | How it is done | File |
|---|---|---|
| Password hashing | Passwords are stored as Werkzeug salted hashes | `seed.py`, `app.py` |
| Two step login | Password, then a 6 digit email OTP. The OTP is made with `secrets`, stored hashed, valid for 2 minutes, one resend, and the second wrong code cancels the login | `app.py`, `security.py` |
| Generic login error | Wrong username, password, role or inactive account all give the same message | `app.py` |
| Safe session | Cookie is HttpOnly, SameSite Lax and expires in 30 minutes | `app.py` |
| Role based access | The role is read from the database on every request, not from the browser. A wrong role gets 403 and is logged | `security.py` |
| Dataset access check | An analyst needs a `dataset_access` row for that dataset, otherwise 404 and a log entry | `analyst_routes.py` |
| Admin safety rules | An admin cannot change their own role or status. The last active admin cannot be demoted or deactivated | `admin_routes.py` |
| File validation | Only CSV and XLSX, max 5 MB, real file signature check, no macros, zip bomb size limit, limits on rows, columns and cell length | `sanitiser.py` |
| Filename cleaning | Folder parts and unsafe characters are removed | `sanitiser.py` |
| Content sanitisation | All cells are read as text so formulas never run. HTML and script content is escaped and marked `[blocked]`. Cells starting with `=`, `+`, `-` or `@` get a leading apostrophe. Hidden control characters are removed | `sanitiser.py` |
| Additive masking | Sensitive numeric columns (financial and medical) get a secret random constant added. See below | `masking.py` |
| Identifier withholding | Names, emails, phones, addresses, Aadhaar, PAN, passport, date of birth and record IDs are found by column name and by content patterns. They are removed before any analysis, chart or PDF is made | `masking.py`, `analysis.py` |
| Small group rule | Groups, periods and results with fewer than 3 records are hidden | `analysis.py` |
| Encryption at rest | The processed data is encrypted with AES-256-GCM using a random 12 byte nonce. The dataset id is used as associated data. The key is kept in `.env` | `crypto_utils.py`, `pipeline.py` |
| Raw file not kept | The uploaded file stays in memory only and is never saved to disk | `pipeline.py` |
| Activity log | Logins, failures, uploads, access changes, downloads and role changes are saved with user, time and IP | `security.py` |

### How the masking works

For each sensitive numeric column the system finds the spread (max minus min). It picks a random sign and a random factor from 1.00 to 9.99, and makes one secret offset `k = sign x factor x spread`. Every value in that column becomes `value + k`.

Example: 90, 100, 130 with `k = 140` become 230, 240, 270. The mean moves, but the standard deviation, order, correlations, group differences and trend changes stay exactly the same. So analysts can still study patterns without seeing real levels. The offset is stored only inside the encrypted data and is never sent to the browser. Mean, median, min and max in the workspace are shown on the "masked scale".

## Setup on Windows

### 1. Install 
- Python 3.10 or newer
- Node.js 18 or newer
- PostgreSQL
- A Gmail account with 2 step verification on and an **App Password** (this is used to send OTP emails)

### 2. Create the database
Open **SQL Shell (psql)** and run:

```sql
CREATE USER privview_user WITH PASSWORD 'YourDbPassword';
CREATE DATABASE privview OWNER privview_user;
```

Then, in a normal terminal, go to the project folder and run the two SQL files in this order:

```
psql -U privview_user -d privview -f backend/schema.sql
psql -U privview_user -d privview -f backend/schema2.sql
```

Note: `schema.sql` deletes and recreates the tables, so run it only on a fresh setup.

### 3. Backend setup
```
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Open `.env` in a text editor and fill in:

| Name | What to put |
|---|---|
| `SECRET_KEY` | any long random text |
| `DATABASE_URL` | `postgresql+psycopg://privview_user:YourDbPassword@localhost:5432/privview` |
| `SMTP_HOST` and `SMTP_PORT` | `smtp.gmail.com` and `587` |
| `SMTP_USER` | the Gmail address that sends the OTP |
| `SMTP_APP_PASSWORD` | the Gmail App Password |
| `DATA_ENCRYPTION_KEY` | a 32 byte key, made with the command below |

Make the encryption key using:

```
python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"
```

Keep this key safe. If it is lost or changed, datasets that are already stored cannot be opened again.

### 4. Create the users
There is no signup page. Open `backend/seed.py` and replace the email addresses with real inboxes you can open, because the OTP is sent there. Then run:

```
python seed.py
```

Default test logins from `seed.py`:

| Username | Password | Role |
|---|---|---|
| admin1 | Admin@123 | admin |
| analyst1 | Analyst@123 | analyst |
| analyst2 | Analyst@456 | analyst |

### 5. Frontend setup
Open a second terminal:

```
cd frontend
npm install
```

## How to run

Use two terminals.

**Terminal 1 (backend)**
```
cd backend
venv\Scripts\activate
python app.py
```
It runs at http://127.0.0.1:5000

**Terminal 2 (frontend)**
```
cd frontend
npm run dev
```
Open http://localhost:5173 in the browser.

## How to try it

1. Log in as `admin1`, choose the admin role, and enter the OTP from your email.
2. Go to **Upload dataset** and upload a CSV or XLSX file. 
3. Open **Datasets**, click **Details**, and grant access to an analyst.
4. Log out and log in as `analyst1` with the analyst role.
5. Open the dataset card, change the filters and download the PDF report.

## File rules

- Only `.csv` and `.xlsx` files, up to 5 MB
- CSV files must be UTF-8
- 2 to 50 columns and up to 50000 rows
- A column is masked only if every filled cell is a number and its name has a financial or medical word (like salary, balance, glucose, systolic). Extra column names to mask can be typed on the upload page
