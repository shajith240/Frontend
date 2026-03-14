# Module 1 — Patient Demographics & Visit History Database
## Professor: Prof. ACS Rao, IIT(ISM) Dhanbad

## Our ER Diagram (submitted)
Entities:
- Patient: PatientID, FirstName, LastName, DateOfBirth, Gender, Phone, Email, Address, Insurance
- Physician: PhysicianID, FirstName, LastName, Speciality, DepartmentID
- Department: DepartmentID, DepartmentName, Location
- Visit: VisitID, VisitDate, Reason, Diagnosis, Status, PatientID, PhysicianID
- Appointment: AppointmentID, AppointmentDateAndTime, Reason, Status, PatientID, PhysicianID
- Referral: ReferralID, ReferralDate, Reason, Status, SourcePhysicianID, TargetPhysicianID, PatientID
- VisitDepartment: VisitID, DepartmentID (junction table — resolves M-to-N)

Relationships:
- Patient to Appointment: 1-to-N
- Patient to Visit: 1-to-N
- Physician to Appointment: 1-to-N
- Physician to Visit: 1-to-N
- Physician to Department: N-to-1
- Patient to Referral: 1-to-N
- Visit to Department: M-to-N via VisitDepartment

## MongoDB Collections
patients, physicians, departments, visits, appointments, referrals, visit_departments, alerts, audit_logs

## PatientID format
PAT-YYYY-NNN (example: PAT-2024-001)

## Stack
Python 3.13, MongoDB Atlas, Streamlit, PyMongo

## Files built so far
- backend/database.py — MongoDB connection with retry logic
- backend/models.py — Pydantic models for all entities
- backend/crud.py — CRUD operations for all collections
- backend/triggers.py — audit_log, age_calculator, visit_frequency_alert, abnormal_vitals, appointment_conflict triggers
- database/seed_data.py — 25 Indian patients with full relational data
- database/queries/aggregations.py — 10 aggregation pipelines with SQL equivalents

## DBMS concepts demonstrated
- Normalization: 9 separate collections
- Triggers: audit_log, age_calculator, visit_frequency_alert, abnormal_vitals, appointment_conflict
- Views: aggregation pipelines as SQL view equivalents
- Stored Procedures: Python functions encapsulating complex multi-step logic
- Constraints: Pydantic validation + MongoDB schema validation
- Indexes: patient_id, name, date_of_birth on patients collection

## Grading rubric
- Code correctness 30%, Individual commits 25%, PR quality 20%, Folder discipline 15%, Commit hygiene 10%

## Business flow
1. Patient registers → stored in patients collection
2. Clerk books appointment → checks physician availability via conflict trigger
3. Physician records visit → linked to patient, physician, department via junction table
4. Physician creates referral → tracks source/target physician
5. System generates views → patient profile, visit history, department stats
