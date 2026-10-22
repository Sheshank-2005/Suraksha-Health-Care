# PRJ_279 — Suraksha Health Care Patient Care Management System

Suraksha Health Care is an academic Flask + SQLite application for demonstrating patient and appointment management, health records, vital monitoring, rule-based symptom screening, patient risk indicators, emergency-event tracking and reporting. It is a prototype, not a production clinical system.

## Main modules
- Role-based demo login (Administrator, Doctor, Receptionist, Patient)
- Password reset with local demo OTP; optional SMTP/Twilio configuration
- Patient CRUD and clinical profiles
- Doctor directory and doctor dashboard
- Appointment scheduling with doctor/time conflict checks
- Health records and structured vital measurements
- Dedicated vitals API with input validation and configurable review flags
- Explainable, rule-based risk indication and symptom screening
- Prescriptions and searchable medicine reference catalogue
- Patient timeline and patient portal endpoint
- Emergency case workflow and in-system notifications
- Analytics, global search, audit log and PDF patient reports

## Run on Windows / VS Code
1. Extract the ZIP. The ZIP contains the project files at its root, so open the extracted folder that contains `app.py` and `requirements.txt`.
2. In VS Code choose **Terminal → New Terminal**.
3. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

4. Start the app:

```powershell
python app.py
```

5. Open `http://127.0.0.1:5000`. Keep the terminal open while using the app. Press `Ctrl+C` to stop it. Alternatively, double-click `RUN_PROJECT.bat`.

## Demo accounts
| Role | Username | Password |
|---|---|---|
| Administrator | `admin` | `admin123` |
| Doctor | `doctor` | `doctor123` |
| Receptionist | `receptionist` | `reception123` |
| Patient | `patient` | `patient123` |

These are demo credentials. Change them and configure a strong secret key before any non-demo deployment.

## Vitals API
- `GET /api/vitals` — list recent records that contain vital measurements
- `GET /api/vitals?patient_id=1` — filter by patient
- `POST /api/vitals` — save vital measurements (Administrator/Doctor)
- `GET /api/patients/1/vitals` — get a patient's vital history
- `GET /api/patients/1/vitals/latest` — get the latest recorded vitals

Example JSON for `POST /api/vitals`:

```json
{
  "patient_id": 1,
  "temperature": 38.2,
  "heart_rate": 96,
  "systolic": 128,
  "diastolic": 82,
  "spo2": 97,
  "weight": 68
}
```

Vitals are stored in the existing `health_records` table so that the dashboard, timeline and PDF report continue to use one consistent data source. API responses include `alerts` and `review_required` for values outside configured demo ranges. These are prompts for qualified review, not diagnoses.

## Tests
After installing requirements, run:

```powershell
python TEST_PROJECT.py
```

The smoke test checks authentication, key endpoints and validation responses. Run it before the final presentation.

## Safety and limitations
The AI screening and risk scoring are transparent academic rule-based demonstrations, not a trained/clinically validated medical AI model. Alert thresholds are illustrative and must be clinically reviewed before real-world use. Do not use real patient data in the demo. The app is not production-ready for sensitive health information without a security review, deployment hardening, and appropriate legal/privacy safeguards.


## Role-specific workspaces (updated)

- **Administrator**: full system overview, patient/doctor management, appointments, clinical modules, reports, analytics, emergency workflow, and audit log.
- **Doctor**: clinical workspace for patients, appointments, health records, vitals, prescriptions, AI screening, emergency cases, and reports. Administrator-only audit log is hidden and blocked by the API.
- **Receptionist**: patient registration/demographic updates, doctor directory, and appointment scheduling. Clinical records, vitals, prescriptions, AI screening, analytics, and emergency clinical views are hidden and protected by server-side role checks.
- **Patient**: redirected to a dedicated personal portal showing only the profile linked to their login, their appointments, health records, prescriptions, and screening history. Global patient listing and clinical staff APIs are denied; a patient cannot request another patient's profile.

The UI hides role-inappropriate sections, but authorization is also enforced on API routes. These demo credentials are for local demonstration only. This academic project is not a certified medical device and must not be used as a substitute for clinical judgment.


## Role-specific workspaces (updated)
The landing dashboard now has a role-specific heading, description, visual theme, and quick actions for Administrator, Doctor, and Receptionist. Patients are redirected to the separate personal health portal. API access remains role-checked on the server; hiding a navigation item is not the security boundary.

## Before a real deployment
This is an academic demonstration, not a production clinical system. Replace the demo secret key, disable demo password-reset OTP display, use individual accounts, configure backups and HTTPS, and conduct security and clinical validation before using any real patient information. Do not use the rule-based screening as a diagnosis.

## Dashboard UI Refresh
The interface has been restyled with a light blue-and-white hospital dashboard theme inspired by the supplied reference: blue header, clean sidebar navigation, role-colored welcome banner, KPI cards, responsive panels, clearer tables, and improved mobile layouts. Existing page IDs and JavaScript hooks are preserved so the existing dashboard features can continue to operate.

## Run on Windows
1. Extract the ZIP.
2. Open the folder that contains `app.py` and `requirements.txt`.
3. Run `python -m pip install -r requirements.txt`.
4. Run `python app.py`.
5. Open `http://127.0.0.1:5000`.

## Backend data expansion (new)

The optional `seed_demo_data.py` script adds fictional records until the database contains at least 50 patients, 10 doctors, 100 appointments, 100 health records/vital entries, 50 prescriptions, 50 rule-based screening entries, and 10 synthetic emergency scenarios. It does not delete existing records and can be rerun to top up the tables without repeatedly adding data once the targets are reached. Appointment slots are checked for conflicts while generating appointments.

Run it from this folder after installing dependencies:

```powershell
python seed_demo_data.py
```

Then restart the app if it is running:

```powershell
python app.py
```

The existing `/api/dashboard` and `/api/analytics` endpoints calculate dashboard metrics and chart series from SQLite queries. The dataset is synthetic, created for demonstration only. Seeded emergency cases are explicitly labelled as synthetic scenarios and must not be treated as real alerts.

### Recommended run sequence for a fresh extraction

```powershell
python -m pip install -r requirements.txt
python seed_demo_data.py
python TEST_PROJECT.py
python app.py
```

If `TEST_PROJECT.py` reports a failure, resolve it before presenting. The smoke test requires the packages in `requirements.txt` to be installed.


## Language selector

The interface includes English, Kannada (ಕನ್ನಡ), and Hindi (हिन्दी). Choose a language from the selector in the dashboard or account pages; the choice is saved in the browser and retained while navigating. Common interface labels and messages are translated locally without sending patient data to an external translation service. Medical names, user-entered content, and some detailed dynamic text may remain in their original language; this is an academic UI translation feature, not a certified medical translation.

## Full-interface language support

The English/Kannada/Hindi selector applies the local translation dictionary first. For text not covered by the dictionary—including many dynamically rendered labels and data—the project also enables Google Translate's page-wide widget. This fallback requires an internet connection and a browser that allows the translation script. Patient-entered/database values may be translated by the external translation service; do not use real sensitive patient data with this academic demo. English resets the page to its original language.


## English, Kannada and Hindi interface

The language selector is available on the dashboard, patient portal, login, forgot-password, reset-password and account-security pages. The selected language is saved in the browser and reused when navigating between pages. Interface translations are handled locally by `static/language.js`; the application does not load a third-party page-translation service or send patient records to one. Dynamic interface messages, labels, placeholders, options, and newly rendered UI elements use the same local glossary.

**Scope note:** this translates the application's interface, not patient-entered names, diagnoses, notes, medicine names, or other clinical/database content. Those values are kept as recorded to avoid changing clinical meaning. The language glossary is maintained in `static/language.js`; add a Kannada and Hindi entry whenever new English UI text is introduced.

### Language verification checklist

1. Start the app and sign in.
2. Select Kannada and visit the dashboard, Patients, Doctors, Appointments, Vitals, Prescriptions, Medicines, Health Records, AI Screening, Emergency, Smart Care, Analytics, Reports, and Audit Log (where permitted by role).
3. Open and close forms, trigger validation/toast messages, search tables, and switch between sections to check dynamically rendered interface text.
4. Repeat in Hindi, then switch back to English.
5. Visit the patient portal and account/password pages; verify the language is retained after navigation.

Clinical terms and AI-screening content should be reviewed by a fluent speaker before real-world healthcare use. This is an academic demonstration, not a clinical product.


## Patient Health Timeline Update

The clinical workspace includes a Patient Health Timeline for Administrator and Doctor roles. Choose a patient to review date-sorted appointments, clinical records, recorded vital signs, prescriptions, AI screening history, and emergency cases. The timeline includes event filters and a brief patient summary. Interface labels are covered by the local English/Kannada/Hindi language switcher; patient-entered and clinical database values are kept unchanged.

The timeline is a summary of records saved in this academic application. AI screening and vital-sign indicators are not a diagnosis and must be reviewed by qualified healthcare professionals.


## Competition upgrade modules
- Follow-up centre for scheduled and missed appointments; reminder actions are logged in-app. External email/SMS delivery requires provider credentials in `.env`.
- Medicine inventory with batch, quantity, expiry, low-stock/expiring/expired status.
- Lab report uploads for PDF/PNG/JPG with role-checked downloads.
- Patient QR PNG generation (requires `qrcode[pil]`). QR contains the local profile URL; use only on a trusted network and share with authorized staff.
- Administrator-only SQLite backup download and validated restore with a pre-restore copy. Keep backups encrypted and access-controlled.
- Administrator-only repeat-safe import of 1,000 synthetic patients from System Tools. Synthetic rows use `@caresphere.invalid` email addresses.
- Limited offline caching for static assets; data actions require the local Flask server and database.

### Security notes
This is an educational demo, not a production clinical system. Change `PATIENTCARE_SECRET_KEY`, configure secure deployment settings, protect uploaded records and backups, and perform a security/privacy review before any real patient use. The AI screening is decision support only and is not a diagnosis.


## Additional final update

The final update adds or tightens these workflows on top of the existing project:

- Patient self-service contact editing (email, phone, address, emergency contact), scoped to the authenticated patient's linked profile.
- Patient portal access to their own lab-report download links; report files are stored outside the public static directory and served through an authenticated, role-checked route.
- Appointment reminder channel selection: in-app reminders are logged to the linked patient account(s); optional email and SMS delivery can be enabled with SMTP/Twilio credentials in `.env`.
- Administrator-only CSV exports for patient, appointment, and health-record data, with export actions recorded in the audit log.
- Account Security now supports changing a password after verifying the current password; new passwords must be at least 10 characters.
- Appointment API validation for patient existence, active doctor selection, date/time formats, status values, and conflicting slots.
- Same-origin guard for browser state-changing requests, a configurable CORS allowlist, configurable session lifetime, and optional secure-cookie setting.

### New optional settings

Copy `.env.example` to `.env` and fill in only the providers you intend to use. Leave SMTP/Twilio fields blank to use in-app reminders. For HTTPS deployment, set `PATIENTCARE_COOKIE_SECURE=1` and configure `PATIENTCARE_SECRET_KEY` to a long random secret. Configure `PATIENTCARE_CORS_ORIGINS` with the exact trusted origins only.

### Final verification

Run `python TEST_PROJECT.py` after installing `requirements.txt`. The tests include basic role checks, invalid input validation, same-origin protection, and administrator-only CSV export. Static language/timeline/report checks do not replace a live browser and security review. Use only synthetic demo data.
## AI screening and interface refresh

The symptom screening module uses transparent, rule-based phrase matching and returns a category, risk band, score indicator, matched factors, explanation, and suggested next step. It is an academic demonstration only, not a validated medical triage or diagnostic system. Emergency warning phrases are surfaced as urgent prompts, but the tool must never be used to rule out an emergency.

The dashboard styling has been refreshed with a consistent clinical teal-and-slate palette, responsive layouts, and clearer AI result/loading/error states. Run `python TEST_AI_SCREENING.py` to check the screening rules. Full live integration testing still requires installing `requirements.txt` and running the Flask application locally.

## Synthetic demo dataset (important)

This package includes a populated SQLite database and `seed_demo_data.py` to ensure the lists are not empty during a demonstration. The dataset includes 1,000 clearly marked synthetic patient profiles, linked appointment, health-record/vitals, prescription, AI-screening history, lab-report demo entries, appointment reminders, medicine inventory, and sample emergency workflow scenarios. These are fictional UI/testing examples, not real patients, validated clinical data, or real prescriptions. Do not use them for medical decisions.

To safely add any missing demo records to a local database without deleting existing rows, run from this folder:

```powershell
python seed_demo_data.py
```

Back up `patientcare.db` before importing. Demo credentials for local testing: `admin / admin123`, `doctor / doctor123`, `receptionist / reception123`, and `patient / patient123`. Change these before any shared or production deployment.
