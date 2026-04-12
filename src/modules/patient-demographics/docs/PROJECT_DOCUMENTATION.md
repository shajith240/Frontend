# Patient Demographics & Visit History Database — Complete Documentation

**Module:** A1 (Category A)
**Course:** DBMS Project
**Professor:** Prof. ACS Rao, IIT(ISM) Dhanbad

---

## Table of Contents

1. [Presentation Script](#presentation-script)
2. [Q&A Preparation](#qa-preparation)
3. [Normalization Deep Dive](#normalization-deep-dive)
4. [Project Documentation (All Blocks)](#project-documentation)
5. [API Endpoints Reference](#api-endpoints-reference)

---

# Presentation Script

## Your Role: Second Presenter (after Dhruv)

### Transition
> "Thank you Dhruv. Now I'll take you through the database design behind everything you just saw — the ER diagram, the relationships, and the key DBMS concepts we implemented."

### ER Diagram Walkthrough
- **Patient to Appointment:** 1:N — one patient can book many appointments
- **Patient to Visit:** 1:N — one patient can have multiple visits
- **Physician to Appointment/Visit:** 1:N each
- **Physician to Department:** N:1 — multiple doctors can belong to same department
- **Patient to Referral:** 1:N
- **Visit to Department:** M:N via VisitDepartment junction table
- **Self-referencing:** Referral has two FKs to Physician (source + target)

### DBMS Concepts
- Normalization: 9 separate collections
- Triggers: 5 total
- Constraints: Pydantic + MongoDB validation
- Indexes: on patient_id, name, date_of_birth

---

# Q&A Preparation

## ER Diagram Questions

**Q: Why use a junction table for Visit and Department?**
> Because it's M:N. Can't store that in either table without redundancy.

**Q: What's the cardinality between Patient and Visit?**
> 1:N. One patient, many visits.

**Q: Why does Referral have two PhysicianID FKs?**
> Self-referencing relationship — source (referring) and target (specialist).

**Q: Difference between Visit and Appointment?**
> Appointment = scheduled future booking. Visit = actual recorded event.

## General DBMS Questions

**Q: What is a foreign key?**
> Attribute in one table referencing the PK of another. E.g., Visit.PatientID → Patient.PatientID.

**Q: What triggers did you implement?**
> 5 triggers: audit_log, age_calculator, visit_frequency_alert, abnormal_vitals, appointment_conflict.

**Q: Why MongoDB over MySQL?**
> Schema flexibility and clean Python integration. DBMS concepts applied at application layer.

## Contact Number Limitation

**Q: What if patient enters wrong phone?**
> Fallback: Email and Address fields. Future: EmergencyContact field (already in schema) or separate PatientContact table.

## PatientID Scale

**Q: How many patients can be created?**
> Format PAT-YYYY-NNN = 999 per year. Scalable to NNNN (9999/year) if needed.

---

# Normalization Deep Dive

## 1NF — First Normal Form
**Rule:** Atomic values, no repeating groups, must have PK.
- Patient table satisfies 1NF: every column holds single value
- Address split into Street, City, State, PostalCode for strict atomicity

## 2NF — Second Normal Form
**Rule:** Must be in 1NF + no partial dependencies (only applies to composite keys).
- VisitDepartment has composite PK (VisitID, DepartmentID)
- No non-key attributes → automatically in 2NF
- **Violation example:** If we stored DepartmentName in VisitDepartment, it depends only on DepartmentID (partial dependency)

## 3NF — Third Normal Form
**Rule:** Must be in 2NF + no transitive dependencies.
- **Violation example:** Physician(PhysicianID, DepartmentID, DepartmentName) — DepartmentName depends on DepartmentID, not PhysicianID
- **Fix:** Move DepartmentName to Department table

## BCNF — Boyce-Codd Normal Form
**Rule:** Must be in 3NF + every determinant must be a superkey.
- Physician table: only FD is PhysicianID → everything else. PhysicianID is superkey. ✓ BCNF
- VisitDepartment: composite PK is only candidate key. ✓ BCNF

## Quick Reference

| Normal Form | Fixes | Check |
|---|---|---|
| 1NF | Atomic values, no repeating groups | Each cell = one value |
| 2NF | Partial dependency | Non-key depends on WHOLE key |
| 3NF | Transitive dependency | Non-key depends only on key |
| BCNF | Remaining anomalies | Every determinant = superkey |

---

# Project Documentation

## BLOCK 1 — Project Metadata

- **Module Number:** A1
- **Module Title:** Patient Demographics & Visit History Database
- **Category:** Category A
- **Submission Date:** 2026-04-12

## BLOCK 2 — Problem Statement & Objectives

### Problem Statement
In traditional hospital environments, patient demographic data, visit records, appointment schedules, and physician referrals are often managed through fragmented, paper-based systems or disconnected digital spreadsheets. This leads to data redundancy, inconsistencies, difficulty in tracking patient history, and scheduling conflicts. The Patient Demographics & Visit History Database addresses these by providing a centralized, normalized database system that stores patient information, maintains complete visit history, automates appointment conflict detection, and manages inter-physician referrals while enforcing referential integrity through proper DBMS principles.

### Module-Specific Objectives
1. Design ER model with 6 entities and 7 relationships including M:N via junction table
2. Implement self-referencing relationship on Physician through Referral
3. Implement 5 database triggers
4. Build 10 aggregation queries equivalent to complex SQL
5. Enforce validation via Pydantic models
6. Seed with 25 realistic Indian patient records
7. Deploy live on Streamlit Cloud

### System Boundaries

**Does:**
- Manage patient demographics, visit history, appointments, referrals
- Generate automated alerts (abnormal vitals, high visit frequency)
- Prevent appointment double-booking
- Maintain audit logs for all CRUD operations

**Does NOT:**
- Handle billing/financial transactions
- Manage prescriptions or pharmacy data
- Handle lab test ordering/results
- Provide user authentication/RBAC
- Store medical images
- Integrate with external HIS/EHR systems

## BLOCK 3 — Functional Requirements

### FR-01 — Core Data Entities (9 collections)
1. **patients** — demographics
2. **physicians** — doctor details
3. **departments** — hospital departments
4. **visits** — clinical visit records
5. **appointments** — scheduled bookings
6. **referrals** — inter-physician referrals
7. **visit_departments** — M:N junction table
8. **alerts** — system-generated clinical alerts
9. **audit_logs** — CRUD audit trail

### FR-02 — Core Query Operations
10 aggregation queries covering: patient visit counts, monthly trends, top diagnoses, per-department patient counts, pending appointments, referral networks, high-frequency visitors, full patient profiles, physician workload, department statistics.

### FR-05 — Automated Clinical Alerts
- Visit frequency alert (>3 visits in 30 days)
- Abnormal vitals alert (BP, HR, temp, SpO2, resp rate)

### FR-06 — Appointment Conflict Prevention
BEFORE INSERT trigger blocks double-booking within ±30 minutes of any scheduled/confirmed appointment.

## BLOCK 4 — ER Design

### Entities & Primary Keys

| Entity | Primary Key | Format |
|---|---|---|
| Patient | PatientID | PAT-YYYY-NNN |
| Physician | PhysicianID | PHY-YYYY-NNN |
| Department | DepartmentID | DEP-YYYY-NNN |
| Visit | VisitID | VIS-YYYY-NNN |
| Appointment | AppointmentID | APT-YYYY-NNN |
| Referral | ReferralID | REF-YYYY-NNN |
| VisitDepartment | Composite (VisitID, DepartmentID) | — |

### Relationships

| Relationship | Cardinality | Participation |
|---|---|---|
| Patient ↔ Appointment | 1:N | Partial / Total |
| Patient ↔ Visit | 1:N | Partial / Total |
| Patient ↔ Referral | 1:N | Partial / Total |
| Physician ↔ Appointment | 1:N | Partial / Total |
| Physician ↔ Visit | 1:N | Partial / Total |
| Physician ↔ Department | N:1 | Total / Partial |
| Visit ↔ Department | M:N (via junction) | Partial / Partial |
| Physician ↔ Referral (source) | 1:N | Partial / Total |
| Physician ↔ Referral (target) | 1:N | Partial / Total |

## BLOCK 5 — Database Schema

See DDL script below for complete schema. Key points:
- All primary keys are VARCHAR(12) for formatted IDs
- Foreign keys enforce referential integrity
- CHECK constraints validate format (regex for PatientID) and ranges (vital signs)
- Composite key on visit_departments junction table

## BLOCK 6 — DDL Script

```sql
CREATE DATABASE patient_demographics_db;
USE patient_demographics_db;

CREATE TABLE departments (
    department_id   VARCHAR(12)  PRIMARY KEY,
    department_name VARCHAR(100) NOT NULL,
    location        VARCHAR(100) NOT NULL,
    created_at      DATETIME     DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE physicians (
    physician_id  VARCHAR(12)  PRIMARY KEY,
    first_name    VARCHAR(50)  NOT NULL,
    last_name     VARCHAR(50)  NOT NULL,
    speciality    VARCHAR(50)  NOT NULL,
    department_id VARCHAR(12)  NOT NULL,
    phone         VARCHAR(15),
    email         VARCHAR(100),
    is_active     BOOLEAN      DEFAULT TRUE,
    created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (department_id) REFERENCES departments(department_id)
);

CREATE TABLE patients (
    patient_id         VARCHAR(12)  PRIMARY KEY
                       CHECK (patient_id REGEXP '^PAT-[0-9]{4}-[0-9]{3}$'),
    first_name         VARCHAR(50)  NOT NULL,
    last_name          VARCHAR(50)  NOT NULL,
    date_of_birth      DATE         NOT NULL CHECK (date_of_birth <= CURDATE()),
    gender             ENUM('male','female','other','prefer_not_to_say') NOT NULL,
    phone              VARCHAR(15)  NOT NULL,
    email              VARCHAR(100),
    street             VARCHAR(100),
    city               VARCHAR(50),
    state              VARCHAR(50),
    postal_code        VARCHAR(10),
    country            VARCHAR(30)  DEFAULT 'India',
    insurance_provider VARCHAR(100),
    policy_number      VARCHAR(50),
    age                INT          CHECK (age >= 0 AND age <= 150),
    blood_group        ENUM('A+','A-','B+','B-','AB+','AB-','O+','O-','unknown') DEFAULT 'unknown',
    is_active          BOOLEAN      DEFAULT TRUE,
    created_at         DATETIME     DEFAULT CURRENT_TIMESTAMP,
    updated_at         DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE visits (
    visit_id      VARCHAR(12)  PRIMARY KEY,
    patient_id    VARCHAR(12)  NOT NULL,
    physician_id  VARCHAR(12)  NOT NULL,
    visit_date    DATE         NOT NULL,
    reason        VARCHAR(200) NOT NULL,
    diagnosis     VARCHAR(200),
    status        ENUM('active','completed','discharged','cancelled') DEFAULT 'active',
    bp_systolic   INT          CHECK (bp_systolic BETWEEN 50 AND 300),
    bp_diastolic  INT          CHECK (bp_diastolic BETWEEN 20 AND 200),
    heart_rate    INT          CHECK (heart_rate BETWEEN 20 AND 300),
    temperature   DECIMAL(4,1) CHECK (temperature BETWEEN 30.0 AND 45.0),
    oxygen_sat    DECIMAL(4,1) CHECK (oxygen_sat BETWEEN 50.0 AND 100.0),
    notes         TEXT,
    follow_up_date DATE,
    created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id)   REFERENCES patients(patient_id),
    FOREIGN KEY (physician_id) REFERENCES physicians(physician_id)
);

CREATE TABLE appointments (
    appointment_id          VARCHAR(12)  PRIMARY KEY,
    patient_id              VARCHAR(12)  NOT NULL,
    physician_id            VARCHAR(12)  NOT NULL,
    appointment_date_and_time DATETIME   NOT NULL,
    reason                  VARCHAR(200) NOT NULL,
    status                  ENUM('scheduled','confirmed','completed','cancelled','no_show') DEFAULT 'scheduled',
    notes                   TEXT,
    cancellation_reason     VARCHAR(200),
    created_at              DATETIME     DEFAULT CURRENT_TIMESTAMP,
    updated_at              DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id)   REFERENCES patients(patient_id),
    FOREIGN KEY (physician_id) REFERENCES physicians(physician_id)
);

CREATE TABLE referrals (
    referral_id          VARCHAR(12)  PRIMARY KEY,
    patient_id           VARCHAR(12)  NOT NULL,
    source_physician_id  VARCHAR(12)  NOT NULL,
    target_physician_id  VARCHAR(12)  NOT NULL,
    referral_date        DATETIME     DEFAULT CURRENT_TIMESTAMP,
    reason               VARCHAR(200) NOT NULL,
    status               ENUM('pending','accepted','rejected','completed') DEFAULT 'pending',
    notes                TEXT,
    created_at           DATETIME     DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id)          REFERENCES patients(patient_id),
    FOREIGN KEY (source_physician_id) REFERENCES physicians(physician_id),
    FOREIGN KEY (target_physician_id) REFERENCES physicians(physician_id)
);

CREATE TABLE visit_departments (
    visit_id      VARCHAR(12) NOT NULL,
    department_id VARCHAR(12) NOT NULL,
    created_at    DATETIME    DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (visit_id, department_id),
    FOREIGN KEY (visit_id)      REFERENCES visits(visit_id),
    FOREIGN KEY (department_id) REFERENCES departments(department_id)
);

CREATE INDEX idx_patients_name ON patients(first_name, last_name);
CREATE INDEX idx_visits_patient ON visits(patient_id);
CREATE INDEX idx_appointments_physician ON appointments(physician_id, appointment_date_and_time);
```

## BLOCK 7 — Queries (10 Total)

| Query | Description | SQL Constructs |
|---|---|---|
| Q-01 | Patients with visit count | LEFT JOIN, GROUP BY, COUNT |
| Q-02 | Visit frequency by month | GROUP BY, YEAR(), MONTH() |
| Q-03 | Top diagnoses | GROUP BY, ORDER BY, LIMIT |
| Q-04 | Unique patients per department | M:N JOIN, COUNT DISTINCT |
| Q-05 | Patients with pending appointments | Multi-JOIN, WHERE IN |
| Q-06 | Referral network summary | GROUP BY, double JOIN on same table |
| Q-07 | High-frequency visitors | GROUP BY, HAVING |
| Q-08 | Full patient profile | 6-table JOIN |
| Q-09 | Physician workload | Subquery JOINs, COALESCE |
| Q-10 | Department statistics | Multi-level JOIN, correlated subquery |

## BLOCK 8 — Triggers, Procedures, Views

### 5 Triggers
1. **audit_log_trigger** — logs all CRUD operations
2. **age_calculator_trigger** — auto-computes age from DOB
3. **visit_frequency_alert_trigger** — alerts if >3 visits in 30 days
4. **abnormal_vitals_trigger** — alerts on out-of-range vitals
5. **appointment_conflict_trigger** — blocks double-booking ±30min

### 3 Stored Procedures
1. sp_create_patient
2. sp_create_appointment (with conflict check)
3. sp_create_referral (with FK validation)

### 5 Views
1. vw_patient_profile
2. vw_visit_frequency_by_month
3. vw_department_statistics
4. vw_physician_workload
5. vw_pending_appointments

## BLOCK 9 — Test Cases

| TC | Description | Expected | Status |
|---|---|---|---|
| TC-01 | Insert valid patient | Success, age auto-computed | PASS |
| TC-02 | Duplicate patient_id | Rejected | PASS |
| TC-03 | Future DOB | Rejected | PASS |
| TC-04 | Search by name | Correct pagination | PASS |
| TC-05 | Appointment conflict | Blocked | PASS |
| TC-06 | Abnormal vitals | Alert generated | PASS |
| TC-07 | High visit frequency | Alert generated | PASS |
| TC-08 | Referral with invalid physician FK | Blocked | PASS |

## BLOCK 10 — Conclusion

### Summary
Built a Patient Demographics & Visit History Database managing patients, physicians, visits, appointments, and referrals. Implements 3NF/BCNF normalization across 9 collections, 5 triggers, 5 views, 3 stored procedures, and 10 aggregation queries. ER design includes 6 entities, 7 relationships, M:N via junction table, and self-referencing Physician-Referral relationship.

### Outcomes
- 10 queries, 5 triggers, 5 views, 3 procedures
- 25 seed patients, 10 physicians, 5 departments
- Live deployed on Streamlit Cloud
- FastAPI REST layer for cross-module data sharing

### Challenges
- M:N relationship resolution via junction table
- Self-referencing Physician FKs in Referral
- Trigger simulation in MongoDB (application layer)
- Appointment conflict time-window logic
- Multi-layer validation (Pydantic + MongoDB)

### Future Enhancements
- Multiple contact numbers per patient
- Role-based access control
- Prescription/medication tracking
- Lab test integration
- Patient portal
- SMS/email notifications

---

# API Endpoints Reference

## Deployment Status

- **Streamlit UI:** DEPLOYED at `https://dbms-project-module1.streamlit.app/`
- **FastAPI (REST endpoints):** NOT YET DEPLOYED — runs locally on `localhost:8000`

## Available Endpoints

Base URL (local): `http://localhost:8000`

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Database status + collection counts |
| GET | `/api/stats` | Aggregate counts across all collections |
| GET | `/api/patients` | List patients with name/gender filters |
| GET | `/api/patients/{patient_id}` | Full patient profile (joins all tables) |
| GET | `/api/patients/{patient_id}/visits` | Visit history for patient |
| GET | `/api/patients/{patient_id}/summary` | Lightweight patient summary |
| GET | `/api/departments` | All hospital departments |
| GET | `/api/physicians` | All physicians with department info |

## How to Share with Other Modules

**Universal Foreign Key:** `patient_id` in format `PAT-YYYY-NNN`

Other modules use this as FK in their own tables to query patient data via our API.

**Example cross-module call:**
```
GET http://<our-api-host>/api/patients/PAT-2024-001/summary
```

Returns:
```json
{
  "patient_id": "PAT-2024-001",
  "first_name": "Rajesh",
  "last_name": "Sharma",
  "age": 41,
  "gender": "male",
  "blood_group": "B+",
  "phone": "+919812345678",
  "is_active": true,
  "active_alerts": 2
}
```

CORS is enabled (`allow_origins=["*"]`) so any module on any port can call the API.
