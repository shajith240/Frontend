# Module 1 — Patient Demographics & Visit History Database

A full-stack patient demographics and visit history management system built with Python, MongoDB Atlas, and Streamlit. This is Module 1 of the AI-Based Clinical Decision Support System for the DBMS course at IIT(ISM) Dhanbad.

## Features

| Page | Description |
|------|-------------|
| **Home Dashboard** | Metric cards (patients, visits, alerts, referrals), recent patients table, recent visits table, active alerts panel |
| **Register Patient** | Full registration form with phone (+91) validation, email format check, DOB validation, auto-generated PAT-YYYY-NNN IDs |
| **Visit History** | Search by patient ID or name, demographic summary card, full visit timeline with physician and department details |
| **Appointments** | Schedule new appointments with department-filtered physician dropdown, conflict detection, filterable appointment list |
| **Referrals** | Create inter-physician referrals, view all referrals with physician names, referral network summary analytics |
| **DBMS Demo** | Professor evaluation page — schema normalization, indexes, live query execution, trigger demos, stored procedures, audit log viewer |

## DBMS Concepts Demonstrated

- **Normalization:** 9 separate collections in 3NF — no data redundancy, VisitDepartment junction table resolves M-to-N
- **Triggers:** 5 simulated SQL triggers — audit_log, age_calculator, visit_frequency_alert, abnormal_vitals, appointment_conflict
- **Aggregation Pipelines (Views):** 10 MongoDB pipelines equivalent to SQL views with JOINs, GROUP BY, HAVING, subqueries
- **Stored Procedures:** 3 multi-step Python functions equivalent to SQL stored procedures
- **Constraints:** Pydantic validation (regex, enums, range checks, cross-field) equivalent to SQL CHECK/NOT NULL/UNIQUE
- **Indexes:** Unique index on patient_id, indexes on name and date_of_birth for fast lookups

## Schema Overview

| Collection | Purpose | Key Fields |
|------------|---------|------------|
| `patients` | Core patient demographics | patient_id (PK), first_name, last_name, date_of_birth, gender, phone, email, address, insurance |
| `physicians` | Physician registry | physician_id (PK), first_name, last_name, speciality, department_id (FK) |
| `departments` | Hospital department master data | department_id (PK), department_name, location |
| `visits` | Clinical visit records | visit_id (PK), patient_id (FK), physician_id (FK), visit_date, reason, diagnosis, status |
| `appointments` | Scheduled appointments | appointment_id (PK), patient_id (FK), physician_id (FK), appointment_date_and_time, reason, status |
| `referrals` | Inter-physician referrals | referral_id (PK), patient_id (FK), source_physician_id (FK), target_physician_id (FK), reason, status |
| `visit_departments` | Junction table (Visit M:N Department) | visit_id (FK), department_id (FK) |
| `alerts` | System-generated clinical alerts | alert_id (PK), patient_id (FK), alert_type, severity, message, is_acknowledged |
| `audit_logs` | Immutable audit trail | log_id (PK), patient_id, action, collection_name, document_id, performed_by, changes |

## Tech Stack

- **Language:** Python 3.13
- **Database:** MongoDB Atlas
- **Frontend:** Streamlit
- **ORM/ODM:** PyMongo + Pydantic v2
- **Environment:** python-dotenv

## Setup Instructions

### 1. Clone the repository

```bash
git clone <repo-url>
cd Frontend/src/modules/patient-demographics
```

### 2. Create virtual environment

```bash
python -m venv venv
source venv/bin/activate    # Linux/macOS
venv\Scripts\activate       # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the `patient-demographics/` directory:

```
MONGODB_URI=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
```

Make sure your IP address is whitelisted in the MongoDB Atlas dashboard.

### 5. Load seed data

```bash
python database/seed_data.py
```

This creates 25 Indian patients with full relational data across all 9 collections.

### 6. Run the application

```bash
streamlit run app.py
```

The app will open at `http://localhost:8501`.

## Project Structure

```
patient-demographics/
├── app.py                           # Main Streamlit entry point
├── .env                             # MongoDB connection string (not committed)
├── requirements.txt                 # Python dependencies
├── README.md                        # This file
├── CLAUDE.md                        # Project coding guidelines
├── backend/
│   ├── database.py                  # MongoDB connection with retry logic
│   ├── models.py                    # Pydantic models for all entities
│   ├── crud.py                      # CRUD operations with trigger wiring
│   └── triggers.py                  # 5 SQL-style trigger simulations
├── database/
│   ├── seed_data.py                 # Seed data generator (25 patients)
│   └── queries/
│       ├── __init__.py
│       └── aggregations.py          # 10 aggregation pipeline queries
├── frontend/
│   ├── __init__.py
│   ├── components/
│   │   ├── __init__.py
│   │   ├── sidebar.py               # Navigation, connection status, quick stats
│   │   └── alerts.py                # Alert display with severity colors
│   └── pages/
│       ├── __init__.py
│       ├── register_patient.py      # Patient registration form
│       ├── visit_history.py         # Visit timeline with search
│       ├── appointments.py          # Scheduling and appointment list
│       ├── referrals.py             # Referral creation and network view
│       └── dbms_demo.py             # DBMS concepts demo panel
└── docs/
    ├── PROJECT_CONTEXT.md           # ER diagram, relationships, business flow
    └── architecture.md              # System architecture documentation
```

## Team

| Name | Role |
|------|------|
| shajith240 | Developer — Module 1 Patient Demographics & Visit History |
