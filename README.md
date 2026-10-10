# PrivView - Stage 4 (admin download, stricter analyst privacy)

Stage 1: login + email OTP + role-based access. Stage 2: admin upload pipeline (sanitise, mask, AES-256-GCM encrypt, store).
Stage 3: analysts see only datasets an admin has granted, analyse the protected copy, download it and export a PDF report.

## Upgrading from Stage 3 (no new packages, no database migration)
Copy the changed files over your project, delete frontend/src/components/Sparkline.jsx, restart Flask, rebuild/restart the frontend.
Existing datasets keep working: identifiers are withheld from analysts at read time, nothing needs re-uploading.

## Upgrading from Stage 2 (no database migration needed)
1. Copy the new/changed files over your project (or use this folder as is).
2. Backend:   cd backend && pip install -r requirements.txt      (adds reportlab)
3. Frontend:  cd frontend && npm install                          (adds recharts)
4. Your .env keeps working (DATA_ENCRYPTION_KEY must stay the same).

## Fresh setup
- PostgreSQL: create database + user, then run backend/schema.sql, then backend/migrate_stage2.sql
- cd backend; copy .env.example to .env and fill it in (SECRET_KEY, DATABASE_URL, SMTP_*, DATA_ENCRYPTION_KEY)
  - key: python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"
- python -m venv venv; activate it; pip install -r requirements.txt; python seed.py

## Run (two terminals)
- Backend:  cd backend && python app.py            (http://127.0.0.1:5000)
- Frontend: cd frontend && npm run dev             (http://localhost:5173)

## Try the analyst flow
1. Log in as admin1 -> Upload dataset (your own CSV/XLSX; text dates and a text category column give the best charts).
2. Datasets -> Details -> "Analyst access" -> Grant access to analyst1.
3. Admin can use Download (list or Details) to get the processed dataset as CSV (sanitised + masked, includes text identifiers).
4. Log out, log in as analyst1 -> dashboard card -> Open analysis workspace.
5. Change measure / compare-by / date range, download the PDF report, press Back. (Analysts get no CSV download.)
6. As admin, Revoke or Delete -> the dataset disappears from the analyst's list.

## Notes
- Analysis is on the "masked scale": the secret masking constant is never removed, so averages/min/max are shifted,
  while spread, correlations, group differences and trend changes are exact.
- Results from fewer than 3 records are hidden.
- Direct identifiers (names, e-mail, phone, address, Aadhaar/PAN/passport, date of birth, record IDs) are detected by column
  name AND by content, and are cut out in analysis.prepare() before anything else runs. Analysts only get aggregates + the PDF.
- Demo data: four synthetic CSVs are provided separately (demo_datasets/). They are NOT part of the application code.
