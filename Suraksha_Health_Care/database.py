import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DATABASE = str(BASE_DIR / 'patientcare.db')

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def _cols(db, table):
    return {r['name'] for r in db.execute(f'PRAGMA table_info({table})').fetchall()}

def _add_column(db, table, column, definition):
    if column not in _cols(db, table):
        db.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')

def init_db():
    db = get_db()
    db.execute('''CREATE TABLE IF NOT EXISTS patients(
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, age INTEGER,
        gender TEXT, phone TEXT, email TEXT, address TEXT DEFAULT '', blood_group TEXT DEFAULT '', allergies TEXT DEFAULT '',
        emergency_contact TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    for c,d in [('address',"TEXT DEFAULT ''"),('blood_group',"TEXT DEFAULT ''"),('allergies',"TEXT DEFAULT ''"),('emergency_contact',"TEXT DEFAULT ''")]: _add_column(db,'patients',c,d)
    db.execute('''CREATE TABLE IF NOT EXISTS doctors(
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, specialization TEXT DEFAULT '',
        phone TEXT DEFAULT '', email TEXT DEFAULT '', availability TEXT DEFAULT 'Mon-Fri', active INTEGER DEFAULT 1)''')
    db.execute('''CREATE TABLE IF NOT EXISTS appointments(
        id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id INTEGER, doctor TEXT, date TEXT, time TEXT,
        status TEXT DEFAULT 'Scheduled', reason TEXT DEFAULT '', reminder_sent INTEGER DEFAULT 0,
        FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE CASCADE)''')
    _add_column(db,'appointments','reminder_sent','INTEGER DEFAULT 0')
    db.execute('''CREATE TABLE IF NOT EXISTS health_records(
        id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id INTEGER, diagnosis TEXT, treatment TEXT, date TEXT,
        notes TEXT DEFAULT '', temperature REAL, heart_rate INTEGER, systolic INTEGER, diastolic INTEGER,
        spo2 REAL, weight REAL, respiratory_rate INTEGER DEFAULT NULL, blood_glucose REAL DEFAULT NULL,
        FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE CASCADE)''')
    for c,d in [('notes',"TEXT DEFAULT ''"),('temperature','REAL'),('heart_rate','INTEGER'),('systolic','INTEGER'),('diastolic','INTEGER'),('spo2','REAL'),('weight','REAL'),('respiratory_rate','INTEGER'),('blood_glucose','REAL')]: _add_column(db,'health_records',c,d)
    db.execute('''CREATE TABLE IF NOT EXISTS medications(
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, category TEXT DEFAULT '',
        dosage_forms TEXT DEFAULT '', common_dose TEXT DEFAULT '', notes TEXT DEFAULT '', active INTEGER DEFAULT 1)''')
    meds=[
        ('Paracetamol','Analgesic/Antipyretic','Tablet / Syrup','','Reference only; use as prescribed'),('Amoxicillin','Antibiotic','Capsule / Suspension','','Prescription required'),('Cetirizine','Antihistamine','Tablet / Syrup','','Reference only; use as prescribed'),('ORS','Rehydration','Sachet','','Prepare according to package directions'),('Salbutamol','Bronchodilator','Inhaler / Nebulizer solution','','Use as prescribed'),
        ('Ibuprofen','NSAID analgesic','Tablet / Suspension','','Use only after clinician/pharmacist advice'),('Naproxen','NSAID analgesic','Tablet','','Use only after clinician/pharmacist advice'),('Diclofenac','NSAID analgesic','Tablet / Gel','', 'Use only as directed by a clinician'),('Loratadine','Antihistamine','Tablet / Syrup','','Reference only; use as prescribed'),('Fexofenadine','Antihistamine','Tablet / Suspension','','Reference only; use as prescribed'),
        ('Pantoprazole','Acid suppression','Tablet','','Use as prescribed'),('Omeprazole','Acid suppression','Capsule / Tablet','','Use as prescribed'),('Famotidine','Acid suppression','Tablet','','Use as prescribed'),('Metformin','Antidiabetic','Tablet','','Prescription required'),('Amlodipine','Antihypertensive','Tablet','','Prescription required'),('Losartan','Antihypertensive','Tablet','','Prescription required'),('Atorvastatin','Lipid-lowering','Tablet','','Prescription required'),('Levothyroxine','Thyroid hormone','Tablet','','Prescription required'),
        ('Montelukast','Respiratory/allergy','Tablet / Chewable tablet','','Prescription/clinician advice required'),('Budesonide','Corticosteroid','Inhaler / Nasal spray','','Use as prescribed'),('Azithromycin','Antibiotic','Tablet / Suspension','','Prescription required'),('Doxycycline','Antibiotic','Capsule / Tablet','','Prescription required'),('Cefixime','Antibiotic','Tablet / Suspension','','Prescription required'),('Cefuroxime','Antibiotic','Tablet / Suspension','','Prescription required'),('Ondansetron','Antiemetic','Tablet / Oral solution','','Use as prescribed'),('Domperidone','Gastrointestinal medicine','Tablet','','Use only on clinician advice'),
        ('Loperamide','Antidiarrheal','Capsule / Tablet','','Follow label; seek care for severe symptoms'),('Lactulose','Laxative','Oral solution','','Use as directed'),('Polyethylene glycol','Laxative','Powder','','Use as directed'),('Ferrous sulfate','Iron supplement','Tablet / Liquid','','Use as prescribed'),('Folic acid','Vitamin supplement','Tablet','','Use as directed'),('Vitamin D3','Vitamin supplement','Capsule / Drops','','Use as directed'),('Vitamin B12','Vitamin supplement','Tablet / Injection','','Use as directed'),('Calcium carbonate','Mineral supplement','Tablet','','Use as directed'),
        ('Aspirin','Antiplatelet/analgesic','Tablet','','Do not start for cardiovascular prevention without clinician advice'),('Clopidogrel','Antiplatelet','Tablet','','Prescription required'),('Insulin (various types)','Antidiabetic','Injection','','Prescription and clinician supervision required'),('Mupirocin','Topical antibiotic','Ointment','','Use as prescribed'),('Clotrimazole','Antifungal','Cream / Lozenge','','Use as directed'),('Hydrocortisone topical','Topical corticosteroid','Cream / Ointment','','Use as directed'),('Artificial tears','Eye lubricant','Eye drops','','Follow package instructions'),('Chlorhexidine mouthwash','Antiseptic','Mouthwash','','Follow product directions'),('Dextromethorphan','Cough suppressant','Syrup / Capsule','','Follow label and pharmacist advice'),('Guaifenesin','Expectorant','Syrup / Tablet','','Follow label and pharmacist advice'),('Acetylcysteine','Mucolytic','Tablet / Sachet / Solution','','Use as directed')
    ]
    db.executemany('INSERT OR IGNORE INTO medications(name,category,dosage_forms,common_dose,notes) VALUES(?,?,?,?,?)',meds)

    db.execute('''CREATE TABLE IF NOT EXISTS medicine_inventory(
        id INTEGER PRIMARY KEY AUTOINCREMENT, medicine TEXT NOT NULL, batch_number TEXT DEFAULT '',
        quantity INTEGER NOT NULL DEFAULT 0, expiry_date TEXT NOT NULL, supplier TEXT DEFAULT '',
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    db.execute('''CREATE TABLE IF NOT EXISTS lab_reports(
        id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id INTEGER NOT NULL, title TEXT NOT NULL,
        file_name TEXT NOT NULL, stored_name TEXT NOT NULL, uploaded_by TEXT, uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE CASCADE)''')
    db.execute('''CREATE TABLE IF NOT EXISTS appointment_reminders(
        id INTEGER PRIMARY KEY AUTOINCREMENT, appointment_id INTEGER NOT NULL, channel TEXT DEFAULT 'in-app',
        status TEXT DEFAULT 'queued', message TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(appointment_id) REFERENCES appointments(id) ON DELETE CASCADE)''')

    db.execute('''CREATE TABLE IF NOT EXISTS prescriptions(
        id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id INTEGER, doctor TEXT, medicine TEXT NOT NULL,
        dosage TEXT DEFAULT '', frequency TEXT DEFAULT '', duration TEXT DEFAULT '', instructions TEXT DEFAULT '',
        date TEXT DEFAULT CURRENT_DATE, status TEXT DEFAULT 'Active',
        FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE CASCADE)''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_screenings(
        id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id INTEGER, symptoms TEXT NOT NULL, risk TEXT,
        category TEXT, recommendation TEXT, risk_score INTEGER DEFAULT 0, factors TEXT DEFAULT '', created_at TEXT,
        FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE SET NULL)''')
    for c,d in [('risk_score','INTEGER DEFAULT 0'),('factors',"TEXT DEFAULT ''")]: _add_column(db,'ai_screenings',c,d)
    db.execute('''CREATE TABLE IF NOT EXISTS emergency_cases(
        id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id INTEGER, reason TEXT NOT NULL, severity TEXT DEFAULT 'Critical',
        status TEXT DEFAULT 'Open', notes TEXT DEFAULT '', created_by TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        resolved_at TEXT, FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE SET NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS notifications(
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, title TEXT, message TEXT, kind TEXT DEFAULT 'info',
        read INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    db.execute('''CREATE TABLE IF NOT EXISTS audit_logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, role TEXT, action TEXT, entity TEXT, entity_id INTEGER,
        details TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    _add_column(db,'audit_logs','details',"TEXT DEFAULT ''")
    db.execute('''CREATE TABLE IF NOT EXISTS app_users(
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, role TEXT NOT NULL,
        password_hash TEXT NOT NULL, patient_id INTEGER, active INTEGER DEFAULT 1, email TEXT DEFAULT '', phone TEXT DEFAULT '',
        reset_code_hash TEXT, reset_token_hash TEXT, reset_expires TEXT, reset_attempts INTEGER DEFAULT 0,
        FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE SET NULL)''')
    for c,d in [('email',"TEXT DEFAULT ''"),('phone',"TEXT DEFAULT ''"),('reset_code_hash','TEXT'),('reset_token_hash','TEXT'),('reset_expires','TEXT'),('reset_attempts','INTEGER DEFAULT 0')]: _add_column(db,'app_users',c,d)
    # Seed patients only if empty.
    if db.execute('SELECT COUNT(*) c FROM patients').fetchone()['c'] == 0:
        db.execute("INSERT INTO patients(name,age,gender,phone,email,blood_group,allergies,emergency_contact) VALUES(?,?,?,?,?,?,?,?)",('Rahul Kumar',21,'Male','9876543210','rahul@example.com','O+','None','+919876543210'))
        db.execute("INSERT INTO patients(name,age,gender,phone,email,blood_group,allergies,emergency_contact) VALUES(?,?,?,?,?,?,?,?)",('Ananya Sharma',24,'Female','9876501234','ananya@example.com','A+','Penicillin','+919876543211'))
    if db.execute('SELECT COUNT(*) c FROM doctors').fetchone()['c'] == 0:
        for x in [('Dr. Ananya Rao','General Medicine','9876500001','ananya.rao@example.com'),('Dr. Vikram Mehta','Cardiology','9876500002','vikram.mehta@example.com'),('Dr. Priya Nair','Pediatrics','9876500003','priya.nair@example.com'),('Dr. Arjun Reddy','Dermatology','9876500004','arjun.reddy@example.com'),('Dr. Kavya Iyer','Orthopedics','9876500005','kavya.iyer@example.com'),('Dr. Rahul Menon','Neurology','9876500006','rahul.menon@example.com'),('Dr. Sneha Kulkarni','ENT','9876500007','sneha.kulkarni@example.com'),('Dr. Aditya Shah','Ophthalmology','9876500008','aditya.shah@example.com'),('Dr. Meera Joshi','Endocrinology','9876500009','meera.joshi@example.com'),('Dr. Kiran Shetty','Pulmonology','9876500010','kiran.shetty@example.com')]: db.execute('INSERT OR IGNORE INTO doctors(name,specialization,phone,email) VALUES(?,?,?,?)',x)
    # Replace numbered placeholder doctor names in existing databases without changing IDs.
    named_roster=[('Dr. Ananya Rao','General Medicine'),('Dr. Vikram Mehta','Cardiology'),('Dr. Priya Nair','Pediatrics'),('Dr. Arjun Reddy','Dermatology'),('Dr. Kavya Iyer','Orthopedics'),('Dr. Rahul Menon','Neurology'),('Dr. Sneha Kulkarni','ENT'),('Dr. Aditya Shah','Ophthalmology'),('Dr. Meera Joshi','Endocrinology'),('Dr. Kiran Shetty','Pulmonology')]
    old=db.execute("SELECT id FROM doctors WHERE name LIKE 'Dr. Demo %' ORDER BY id").fetchall()
    for idx,row in enumerate(old):
        if idx < len(named_roster): db.execute('UPDATE doctors SET name=?,specialization=? WHERE id=?',(named_roster[idx][0],named_roster[idx][1],row['id']))
    # Ensure the medicine catalogue is expanded even when the table already contains a few entries.
    db.executemany('INSERT OR IGNORE INTO medications(name,category,dosage_forms,common_dose,notes) VALUES(?,?,?,?,?)',meds)

    if db.execute('SELECT COUNT(*) c FROM appointments').fetchone()['c'] == 0:
        db.execute("INSERT INTO appointments(patient_id,doctor,date,time,status,reason) VALUES(?,?,?,?,?,?)",(1,'Dr. Kumar','2026-09-23','10:30','Scheduled','Routine check-up'))
    if db.execute('SELECT COUNT(*) c FROM health_records').fetchone()['c'] == 0:
        db.execute("INSERT INTO health_records(patient_id,diagnosis,treatment,date,notes,temperature,heart_rate,systolic,diastolic,spo2,weight) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(1,'Fever','Rest and hydration','2026-09-22','Monitor temperature.',38.2,92,128,82,97,68.5))
    if db.execute('SELECT COUNT(*) c FROM ai_screenings').fetchone()['c'] == 0:
        db.execute("INSERT INTO ai_screenings(patient_id,symptoms,risk,category,recommendation,risk_score,factors,created_at) VALUES(?,?,?,?,?,?,?,?)",(1,'fever and cough','Medium','Respiratory','Review with a healthcare professional.',45,'fever; respiratory symptoms','2026-09-22 15:30'))
    demo=[('admin','Administrator','admin123','admin@example.com','+919876540001',None),('doctor','Doctor','doctor123','doctor@example.com','+919876540002',None),('receptionist','Receptionist','reception123','reception@example.com','+919876540003',None),('patient','Patient','patient123','rahul@example.com','+919876543210',1)]
    for username,role,password,email,phone,pid in demo:
        row=db.execute('SELECT id FROM app_users WHERE username=?',(username,)).fetchone()
        if not row: db.execute('INSERT INTO app_users(username,role,password_hash,email,phone,patient_id) VALUES(?,?,?,?,?,?)',(username,role,generate_password_hash(password),email,phone,pid))
        else: db.execute('UPDATE app_users SET role=?,email=COALESCE(NULLIF(email,\'\'),?),phone=COALESCE(NULLIF(phone,\'\'),?),patient_id=COALESCE(patient_id,?) WHERE username=?',(role,email,phone,pid,username))
    for table,col in [('appointments','date'),('health_records','date'),('ai_screenings','created_at'),('audit_logs','created_at')]: db.execute(f'CREATE INDEX IF NOT EXISTS idx_{table}_{col.replace("_","")} ON {table}({col})')
    db.commit(); db.close()
