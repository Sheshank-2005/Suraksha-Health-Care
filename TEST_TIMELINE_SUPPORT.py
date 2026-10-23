"""Static integration checks for the Suraksha Health Care patient health timeline.
Run with: python TEST_TIMELINE_SUPPORT.py
This does not replace an authenticated browser/API integration test.
"""
from pathlib import Path
import ast
root=Path(__file__).resolve().parent
app=(root/"app.py").read_text(encoding="utf-8")
js=(root/"static"/"script.js").read_text(encoding="utf-8")
html=(root/"templates"/"index.html").read_text(encoding="utf-8")
lang=(root/"static"/"language.js").read_text(encoding="utf-8")
ast.parse(app)
assert "@app.get('/api/timeline/<int:pid>')" in app
assert "@roles('Administrator','Doctor')" in app
for event_type in ("Health Record","Vital Signs","Appointment","Prescription","AI Screening","Emergency"):
    assert f"'type':'{event_type}'" in app, event_type
for element_id in ("timeline","timelinePatient","timelineFilter","patientTimelineEvents"):
    assert f'id="{element_id}"' in html, element_id
assert "loadPatientTimeline" in js and "renderPatientTimeline" in js
assert "'Health Timeline'" in lang and "'Health Timeline'" in lang
print("Patient timeline static integration checks: PASS")
print("Python AST, route guard, six event types, page controls, UI hooks and language labels checked.")
