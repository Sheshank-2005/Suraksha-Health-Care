"""Dependency-free structural checks for Suraksha Health Care's extended feature modules.
Run: python TEST_FEATURES_STATIC.py
These checks verify source wiring, not live browser or clinical validation.
"""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parent
app_text = (ROOT / 'app.py').read_text(encoding='utf-8')
db_text = (ROOT / 'database.py').read_text(encoding='utf-8')
feature_js = (ROOT / 'static' / 'features.js').read_text(encoding='utf-8')
index = (ROOT / 'templates' / 'index.html').read_text(encoding='utf-8')

ast.parse(app_text)
ast.parse(db_text)
required_routes = [
    "'/api/inventory'", "'/api/labs'", "'/api/patients/<int:pid>/qr'",
    "'/api/admin/backup'", "'/api/admin/restore'",
    "'/api/admin/import-demo-patients'", "'/api/admin/export/<dataset>'",
    "'/api/followups'", "'/api/analytics'", "'/api/audit'",
    "'/api/appointments/<int:aid>/remind'", "'/api/patient-portal/profile'",
]
for route in required_routes:
    assert route in app_text, f'Missing route: {route}'
for table in ['medicine_inventory', 'lab_reports', 'appointment_reminders', 'audit_logs', 'notifications', 'app_users']:
    assert f'CREATE TABLE IF NOT EXISTS {table}' in db_text, f'Missing database table: {table}'
for fn in ['loadLabs', 'loadInventory', 'editInventory', 'deleteInventory', 'loadFollowups', 'sendFollowupReminder', 'importDemoPatients', 'downloadPatientQR']:
    assert f'function {fn}' in feature_js or f'async function {fn}' in feature_js, f'Missing UI function: {fn}'
for section in ['labs', 'inventory', 'followups', 'systemtools']:
    assert f'id="{section}"' in index, f'Missing UI section: {section}'
assert 'init_db()' in app_text[app_text.find("def database_restore"):app_text.find("def import_demo_patients")], 'Restore should reapply schema migrations'
print('Suraksha Health Care feature static checks: PASS')
print('Checked extended API routes, database tables, feature UI hooks, and restore migration wiring.')
print('Note: live Flask/API tests and browser workflows must still be run on a machine with requirements installed.')
