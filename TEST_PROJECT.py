"""Suraksha Health Care smoke tests. Run after installing requirements: python TEST_PROJECT.py"""
import os
os.environ.setdefault('PATIENTCARE_SECRET_KEY', 'test-key')
from app import app

client = app.test_client()

# Health endpoint must be public.
r = client.get('/health')
assert r.status_code == 200 and r.get_json().get('status') == 'ok', r.data

# API endpoints must require a session.
assert client.get('/api/dashboard').status_code == 401

with client.session_transaction() as s:
    s['logged_in'] = True
    s['username'] = 'admin'
    s['role'] = 'Administrator'

for path in ['/api/dashboard', '/api/patients', '/api/appointments', '/api/records',
              '/api/vitals', '/api/ai/history', '/api/notifications', '/api/analytics',
              '/api/emergency', '/api/medications']:
    r = client.get(path)
    assert r.status_code == 200, (path, r.status_code, r.data[:250])

# Patient vitals endpoints should return data for an existing seeded patient.
r = client.get('/api/patients/1/vitals')
assert r.status_code == 200, (r.status_code, r.data[:250])
r = client.get('/api/patients/1/vitals/latest')
assert r.status_code == 200, (r.status_code, r.data[:250])

# Invalid vital values must be rejected before any database write.
r = client.post('/api/vitals', json={'patient_id': 1, 'spo2': 150})
assert r.status_code == 400, (r.status_code, r.data[:250])

# Required fields are validated for health records.
r = client.post('/api/records', json={'patient_id': 1, 'diagnosis': ''})
assert r.status_code == 400, (r.status_code, r.data[:250])

# Role-based access: receptionist cannot access clinical records; patient sees only own portal.
with client.session_transaction() as s:
    s.clear(); s.update(logged_in=True, username='receptionist', role='Receptionist', patient_id=None)
assert client.get('/api/patients').status_code == 200
assert client.get('/api/appointments').status_code == 200
assert client.get('/api/records').status_code == 403
assert client.get('/api/analytics').status_code == 403
with client.session_transaction() as s:
    s.clear(); s.update(logged_in=True, username='doctor', role='Doctor', patient_id=None)
assert client.get('/api/records').status_code == 200
assert client.get('/api/audit').status_code == 403
with client.session_transaction() as s:
    s.clear(); s.update(logged_in=True, username='patient', role='Patient', patient_id=1)
assert client.get('/').status_code == 200
assert b'My Appointments' in client.get('/').data
assert client.get('/api/patient-portal').status_code == 200
assert client.get('/api/patients').status_code == 403
assert client.get('/api/records').status_code == 403
assert client.get('/api/patients/2').status_code == 403
# Patient self-service can only change their own contact fields and validates input.
r = client.put('/api/patient-portal/profile', json={'email':'not-an-email','phone':'123'})
assert r.status_code == 400, (r.status_code, r.data[:250])
# Same-origin guard rejects a cross-origin state-changing browser request.
r = client.put('/api/patient-portal/profile', headers={'Origin':'https://attacker.example'}, json={'email':'patient@example.com'})
assert r.status_code == 403, (r.status_code, r.data[:250])
# Sensitive CSV exports are administrator-only.
with client.session_transaction() as s:
    s.clear(); s.update(logged_in=True, username='doctor', role='Doctor', patient_id=None)
assert client.get('/api/admin/export/patients').status_code == 403
with client.session_transaction() as s:
    s.clear(); s.update(logged_in=True, username='admin', role='Administrator', patient_id=None)
r = client.get('/api/admin/export/patients')
assert r.status_code == 200 and r.mimetype == 'text/csv', (r.status_code, r.data[:250])
# Appointment payload validation blocks malformed dates and unknown statuses.
r = client.post('/api/appointments', json={'patient_id':1,'doctor':'Dr. Ananya Rao','date':'not-a-date','time':'10:30'})
assert r.status_code == 400, (r.status_code, r.data[:250])

print('Suraksha Health Care smoke tests: PASS')
