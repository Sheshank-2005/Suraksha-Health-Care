"""Static checks for Suraksha Health Care PDF report design assets and implementation."""
from pathlib import Path
import ast
root = Path(__file__).resolve().parent
app_text = (root / 'app.py').read_text(encoding='utf-8')
assert "@app.get('/api/reports/patient/<int:pid>')" in app_text
assert "RLImage(portrait_path" in app_text
assert "PATIENT HEALTH REPORT" in app_text
assert "AI-Assisted Screening History" in app_text
assert "Suraksha Health Care · Confidential patient information" in app_text
assert (root / 'static' / 'ai_doctor.png').is_file()
assert (root / 'static' / 'ai_doctor.png').stat().st_size > 5000
ast.parse(app_text)
print('PASS: PDF route, report sections, bundled AI doctor illustration, and Python syntax.')
print('NOTE: These are static checks; live Flask/PDF rendering requires project dependencies.')
