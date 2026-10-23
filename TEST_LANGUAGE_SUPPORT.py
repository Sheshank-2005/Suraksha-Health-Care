"""Dependency-free static checks for Suraksha Health Care's local language switcher."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LANG = (ROOT / "static" / "language.js").read_text(encoding="utf-8")
TEMPLATES = ROOT / "templates"

assert "translations.kn" in LANG and "translations.hi" in LANG
assert "caresphere-language" in LANG, "Selected language should persist in browser storage"
assert "MutationObserver" in LANG, "Dynamically rendered UI should be translated"
assert "document.documentElement.lang=lang" in LANG, "Document language should follow selection"
assert "translate.google.com" not in LANG and "google.translate" not in LANG, (
    "Interface translation should remain local and must not send clinical page content to a third party"
)

for template in TEMPLATES.glob("*.html"):
    source = template.read_text(encoding="utf-8")
    assert "language.js" in source, f"Language switcher missing from {template.name}"
    assert 'value="kn"' in source and 'value="hi"' in source, (
        f"Kannada/Hindi options missing from {template.name}"
    )

for phrase in ["Dashboard", "Patients", "Appointments", "AI Screening", "Generate PDF", "Patient Portal"]:
    assert phrase in LANG, f"Expected interface phrase not present in glossary: {phrase}"

print("Local language support static checks: PASS")
print("Checked: language persistence, dynamic UI observer, local-only translation, and all HTML templates.")
print("Note: these checks do not replace interactive browser testing or fluent-speaker review.")
