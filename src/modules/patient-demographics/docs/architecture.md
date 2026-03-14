# System Architecture — Module 1 Patient Demographics & Visit History

## Overview

Module 1 is the foundational data layer of the AI-Based Clinical Decision Support System. It owns the `patient_id` (format: `PAT-YYYY-NNN`) which serves as the universal foreign key across all 50 modules in the system. Every other module — from Lab Results (Module 2) to Pharmacy (Module 14) — references patients through this identifier.

The module follows a three-tier architecture:

```
┌─────────────────────────────────┐
│         Streamlit Frontend      │   app.py + frontend/pages/*.py
│    (Browser — port 8501)        │   frontend/components/*.py
├─────────────────────────────────┤
│         Backend Logic           │   backend/crud.py
│    (CRUD + Triggers + Models)   │   backend/triggers.py
│                                 │   backend/models.py
├─────────────────────────────────┤
│       MongoDB Atlas             │   backend/database.py
│  (patient_demographics_db)      │   9 collections
└─────────────────────────────────┘
```

## How This Module Connects to Other Modules

The `patient_id` field (`PAT-YYYY-NNN`) is the integration key. When other modules need patient information, they query the `patients` collection using this ID:

```
Module 1 (Patient Demographics)
    patients.patient_id ────► Module 2  (Lab Results)     lab_results.patient_id
                         ────► Module 3  (Radiology)       imaging_orders.patient_id
                         ────► Module 5  (Billing)         invoices.patient_id
                         ────► Module 7  (Nursing)         nursing_notes.patient_id
                         ────► Module 14 (Pharmacy)        prescriptions.patient_id
                         ────► ...all 50 modules
```

The `alerts` collection feeds into the Master DB global alerts view, which aggregates alerts from all modules into a single dashboard for clinical staff.

The `audit_logs` collection contributes to the system-wide audit trail required for compliance.

## Data Flow

The data flow matches our submitted DFD (Data Flow Diagram):

### Patient Registration Flow

```
Registration Desk ──► [Validation] ──► patients collection
                                   ──► age_calculator_trigger fires
                                   ──► audit_log_trigger fires
                                   ──► Generated PAT-YYYY-NNN returned
```

1. Receptionist fills the registration form (Register Patient page)
2. Pydantic model validates all fields (phone format, DOB not future, required fields)
3. `create_patient()` in crud.py fires the `age_calculator_trigger` to compute age from DOB
4. Patient document is inserted into the `patients` collection
5. `audit_log_trigger` writes a CREATE entry to `audit_logs`
6. The generated `patient_id` is returned to the frontend

### Appointment Booking Flow

```
Receptionist ──► [Select Patient + Physician] ──► appointment_conflict_trigger
                                               ──► (conflict?) ──► ABORT with error
                                               ──► (no conflict?) ──► appointments collection
                                               ──► audit_log_trigger fires
```

1. Receptionist selects patient and physician, chooses date/time
2. `create_appointment()` fires `appointment_conflict_trigger` BEFORE insertion
3. Trigger checks for existing scheduled/confirmed appointments within a 30-minute window
4. If conflict: raises ValueError, appointment is NOT created, user sees error
5. If no conflict: appointment inserted, `audit_log_trigger` writes to `audit_logs`

### Clinical Visit Flow

```
Physician ──► [Record Visit + Vitals] ──► visits collection
                                       ──► audit_log_trigger fires
                                       ──► visit_frequency_alert_trigger fires
                                       ──► (>3 visits in 30 days?) ──► alerts collection
                                       ──► abnormal_vitals_trigger fires
                                       ──► (out of range?) ──► alerts collection
                                       ──► [Link Department] ──► visit_departments collection
```

1. Physician records visit with reason, diagnosis, and optional vital signs
2. `create_visit()` verifies patient and physician exist via FK checks
3. Document inserted into `visits` collection
4. `audit_log_trigger` logs the CREATE action
5. `visit_frequency_alert_trigger` counts visits in the last 30 days — if >3, creates HIGH alert
6. `abnormal_vitals_trigger` checks each vital sign against normal ranges — creates alerts for abnormals
7. `link_visit_department()` inserts junction record into `visit_departments`

### Referral Flow

```
Physician ──► [Select Patient + Source + Target] ──► referrals collection
                                                  ──► audit_log_trigger fires
```

1. Referring physician selects patient, source physician (self), and target specialist
2. `create_referral()` verifies all three entities exist
3. Referral inserted with status `pending`
4. `audit_log_trigger` logs the CREATE action

## Collection Relationships

```
                    ┌──────────────┐
                    │  departments │
                    └──────┬───────┘
                           │ 1
                           │
                           │ N
                    ┌──────┴───────┐        ┌───────────────────┐
                    │  physicians  │────────►│  visit_departments│
                    └──┬───────┬───┘        │  (junction table) │
                       │       │            └─────┬─────────────┘
                    1  │       │ 1                 │
                       │       │              N    │    N
                    N  │       │ N         ┌───────┴──────┐
              ┌────────┘       └──────┐    │    visits    │
              │                       │    └───────┬──────┘
       ┌──────┴──────┐        ┌───────┴──────┐     │ N
       │ appointments│        │  referrals   │     │
       └──────┬──────┘        │ (source_phy  │     │ 1
              │ N             │  target_phy) │  ┌──┴──────┐
              │               └──────┬───────┘  │ patients│
              │ 1                    │ N        └──┬──┬───┘
              └──────────────────────┴─────────────┘  │
                                                      │ 1
                                          ┌───────────┴──┐
                                          │   alerts     │ N
                                          ├──────────────┤
                                          │  audit_logs  │ N
                                          └──────────────┘
```

Key relationships:
- **Patient 1:N Visit** — a patient can have many visits
- **Patient 1:N Appointment** — a patient can have many appointments
- **Patient 1:N Referral** — a patient can be referred multiple times
- **Physician 1:N Visit** — a physician handles many visits
- **Physician 1:N Appointment** — a physician has many appointments
- **Physician N:1 Department** — each physician belongs to one department
- **Visit M:N Department** — resolved via the `visit_departments` junction table
- **Referral → Physician (x2)** — each referral has a source and target physician FK

## Trigger Firing Sequence

All triggers fire automatically inside CRUD operations. The caller never invokes them directly.

| CRUD Operation | Triggers Fired (in order) | Timing |
|---|---|---|
| `create_patient()` | `age_calculator_trigger` → `audit_log_trigger` | BEFORE INSERT → AFTER INSERT |
| `get_patient_by_id()` | `audit_log_trigger` | AFTER READ |
| `update_patient()` | `age_calculator_trigger` (if DOB changed) → `audit_log_trigger` | BEFORE UPDATE → AFTER UPDATE |
| `create_visit()` | `audit_log_trigger` → `visit_frequency_alert_trigger` → `abnormal_vitals_trigger` | AFTER INSERT (x3) |
| `create_appointment()` | `appointment_conflict_trigger` → `audit_log_trigger` | BEFORE INSERT → AFTER INSERT |
| `create_referral()` | `audit_log_trigger` | AFTER INSERT |

The `appointment_conflict_trigger` is the only BEFORE trigger — it raises a `ValueError` to abort the insert if a conflict is detected, exactly like a SQL trigger raising `SIGNAL SQLSTATE '45000'`.

All other triggers are AFTER triggers — they execute after the primary write succeeds, and their failures are swallowed (logged to console) so they never abort the primary operation.
