"""Offline structural checks for the Suraksha Health Care project bundle."""
import ast, sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parent
for filename in ('app.py','database.py','ai_assistant.py'):
    ast.parse((ROOT/filename).read_text(encoding='utf-8'), filename=filename)
app=(ROOT/'app.py').read_text(encoding='utf-8')
html=(ROOT/'templates'/'index.html').read_text(encoding='utf-8')
js=(ROOT/'static'/'features.js').read_text(encoding='utf-8')
required_routes=['/api/inventory','/api/labs','/api/patients/<int:pid>/qr','/api/admin/backup','/api/admin/restore','/api/admin/import-demo-patients','/api/followups']
for route in required_routes: assert route in app, f'Missing route: {route}'
for section in ['labs','inventory','followups','systemtools']: assert f'id="{section}"' in html, f'Missing UI section: {section}'
assert 'serviceWorker.register' in js
con=sqlite3.connect(ROOT/'patientcare.db')
assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
tables={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
assert {'patients','appointments','health_records','medicine_inventory','lab_reports','appointment_reminders'} <= tables
count=con.execute("SELECT COUNT(*) FROM patients WHERE email LIKE 'demo.patient.%@caresphere.invalid'").fetchone()[0]
assert count==1000, f'Expected 1000 synthetic patients, found {count}'
print('PASS: Python syntax, feature routes, UI sections, offline asset registration, SQLite integrity, and 1,000 synthetic demo patients.')
con.close()
