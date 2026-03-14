# Patient Demographics & Visit History Database
## Project context
- Academic DBMS project at IIT(ISM) Dhanbad
- Module 1 of 50 in AI-Based Clinical Decision Support System
- Professor: Prof. ACS Rao
- Stack: Python 3.13, MongoDB Atlas, Streamlit, PyMongo, FastAPI
- Folder: src/modules/patient-demographics/

## Rules for every file you write
- Always use python-dotenv to load .env
- Always add type hints to every function
- Always add docstrings to every class and function
- Never hardcode credentials
- Always handle exceptions with try/except
- Use patient_id as the universal foreign key (format: PAT-YYYY-NNN)

## Git commit rules
- Format: type(patient-demographics): description
- Types: feat, fix, chore, docs, refactor
- Examples:
  - feat(patient-demographics): add patient registration CRUD operations
  - fix(patient-demographics): correct date validation in visit model
  - docs(patient-demographics): add schema documentation

## MongoDB collections
- patients, visits, appointments, referrals, alerts, audit_logs

## After every file
- Run: git add <file> && git commit -m "..."
- Do NOT push until told to
