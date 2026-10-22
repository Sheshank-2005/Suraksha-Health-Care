import os, secrets, hashlib, smtplib, urllib.parse, urllib.request, base64, io, json, csv, sqlite3, shutil, random, string
from email.message import EmailMessage
from datetime import datetime, date, timedelta
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file, abort
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
load_dotenv()
from database import get_db, init_db
from ai_assistant import analyze_symptoms

app=Flask(__name__); app.config['MAX_CONTENT_LENGTH']=12*1024*1024; app.secret_key=os.environ.get('PATIENTCARE_SECRET_KEY','prj279-demo-secret-key-change-in-production'); app.config['JSON_SORT_KEYS']=False
app.config['SESSION_COOKIE_HTTPONLY']=True; app.config['SESSION_COOKIE_SAMESITE']='Lax'; app.config['SESSION_COOKIE_SECURE']=os.getenv('PATIENTCARE_COOKIE_SECURE','0')=='1'; app.config['PERMANENT_SESSION_LIFETIME']=timedelta(minutes=int(os.getenv('PATIENTCARE_SESSION_MINUTES','60'))); CORS(app, origins=[x.strip() for x in os.getenv('PATIENTCARE_CORS_ORIGINS','http://127.0.0.1:5000,http://localhost:5000').split(',') if x.strip()]); init_db()

@app.before_request
def same_origin_guard():
    # Browser-origin guard for state-changing requests; requests without Origin (e.g. CLI/tests) remain supported.
    if request.method in ('POST','PUT','PATCH','DELETE'):
        origin=request.headers.get('Origin')
        if origin:
            parsed=urllib.parse.urlparse(origin)
            if not parsed.netloc or parsed.netloc.lower()!=request.host.lower():
                return jsonify(error='Cross-origin state-changing request blocked.'),403

def audit(action,entity='system',entity_id=None,details=''):
    try:
        db=get_db(); db.execute('INSERT INTO audit_logs(username,role,action,entity,entity_id,details) VALUES(?,?,?,?,?,?)',(session.get('username','unknown'),session.get('role','Unknown'),action,entity,entity_id,details)); db.commit(); db.close()
    except Exception: pass

def notify(username,title,message,kind='info'):
    if not username:return
    db=get_db(); db.execute('INSERT INTO notifications(username,title,message,kind) VALUES(?,?,?,?)',(username,title,message,kind)); db.commit(); db.close()

def login_required(fn):
    @wraps(fn)
    def w(*a,**kw):
        if not session.get('logged_in'): return jsonify({'error':'Authentication required'}),401
        return fn(*a,**kw)
    return w

def roles(*allowed):
    def deco(fn):
        @wraps(fn)
        def w(*a,**kw):
            if not session.get('logged_in'): return jsonify({'error':'Authentication required'}),401
            if session.get('role') not in allowed: return jsonify({'error':'Permission denied'}),403
            return fn(*a,**kw)
        return w
    return deco

@app.context_processor
def inject_user(): return {'current_username':session.get('username','Admin'),'current_role':session.get('role','Administrator')}
@app.route('/')
def home():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if session.get('role') == 'Patient':
        return render_template('patient_portal.html', current_username=session.get('username'), current_role=session.get('role'))
    return render_template('index.html')

# ---- password reset ----
def _hash(v): return hashlib.sha256(v.encode()).hexdigest()
def _send_email(to,code,reset_url):
    host=os.getenv('PATIENTCARE_SMTP_HOST',''); user=os.getenv('PATIENTCARE_SMTP_USER',''); pwd=os.getenv('PATIENTCARE_SMTP_PASSWORD',''); sender=os.getenv('PATIENTCARE_SMTP_FROM',user); port=int(os.getenv('PATIENTCARE_SMTP_PORT','587'))
    if not host or not user or not pwd or not sender:return False,'SMTP is not configured.'
    msg=EmailMessage(); msg['Subject']='Suraksha Health Care password reset code'; msg['From']=sender; msg['To']=to; msg.set_content(f'Your reset code is {code}. Reset link: {reset_url}. It expires in 10 minutes.')
    try:
        if port==465:
            with smtplib.SMTP_SSL(host,port,timeout=20) as s:s.login(user,pwd);s.send_message(msg)
        else:
            with smtplib.SMTP(host,port,timeout=20) as s:s.starttls();s.login(user,pwd);s.send_message(msg)
        return True,'sent'
    except Exception as e:return False,str(e)
def _send_sms(to,code,reset_url):
    sid=os.getenv('PATIENTCARE_TWILIO_ACCOUNT_SID',''); token=os.getenv('PATIENTCARE_TWILIO_AUTH_TOKEN',''); sender=os.getenv('PATIENTCARE_TWILIO_FROM','')
    if not sid or not token or not sender:return False,'SMS service is not configured.'
    data=urllib.parse.urlencode({'To':to,'From':sender,'Body':f'Suraksha Health Care reset code {code}. {reset_url} Expires in 10 minutes.'}).encode(); req=urllib.request.Request(f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json',data=data,method='POST'); req.add_header('Authorization','Basic '+base64.b64encode(f'{sid}:{token}'.encode()).decode())
    try:
        with urllib.request.urlopen(req,timeout=15):pass
        return True,'sent'
    except Exception as e:return False,str(e)

def _send_notice_email(to,subject,body):
    host=os.getenv('PATIENTCARE_SMTP_HOST',''); user=os.getenv('PATIENTCARE_SMTP_USER',''); pwd=os.getenv('PATIENTCARE_SMTP_PASSWORD',''); sender=os.getenv('PATIENTCARE_SMTP_FROM',user); port=int(os.getenv('PATIENTCARE_SMTP_PORT','587'))
    if not host or not user or not pwd or not sender:return False,'SMTP is not configured.'
    msg=EmailMessage();msg['Subject']=subject;msg['From']=sender;msg['To']=to;msg.set_content(body)
    try:
        if port==465:
            with smtplib.SMTP_SSL(host,port,timeout=20) as server:server.login(user,pwd);server.send_message(msg)
        else:
            with smtplib.SMTP(host,port,timeout=20) as server:server.starttls();server.login(user,pwd);server.send_message(msg)
        return True,'sent'
    except Exception as exc:return False,str(exc)

def _send_notice_sms(to,body):
    sid=os.getenv('PATIENTCARE_TWILIO_ACCOUNT_SID','');token=os.getenv('PATIENTCARE_TWILIO_AUTH_TOKEN','');sender=os.getenv('PATIENTCARE_TWILIO_FROM','')
    if not sid or not token or not sender:return False,'SMS service is not configured.'
    data=urllib.parse.urlencode({'To':to,'From':sender,'Body':body}).encode();req=urllib.request.Request(f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json',data=data,method='POST');req.add_header('Authorization','Basic '+base64.b64encode(f'{sid}:{token}'.encode()).decode())
    try:
        with urllib.request.urlopen(req,timeout=15):pass
        return True,'sent'
    except Exception as exc:return False,str(exc)
def _mask_email(v): return (v[:1]+'***@'+v.split('@',1)[1]) if v and '@' in v else 'email on file'
def _mask_phone(v):
    d=''.join(x for x in str(v or '') if x.isdigit()); return '+'+d[:2]+'******'+d[-2:] if len(d)>=6 else 'phone on file'
@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        u=request.form.get('username','').strip().lower(); p=request.form.get('password',''); db=get_db(); row=db.execute('SELECT * FROM app_users WHERE username=? AND active=1',(u,)).fetchone(); db.close()
        if row and check_password_hash(row['password_hash'],p): session.clear(); session.update(logged_in=True,username=u,role=row['role'],patient_id=row['patient_id']); session.permanent=True; audit('Login','session'); return redirect(url_for('home'))
        return render_template('login.html',error='Invalid username or password')
    return render_template('login.html')
@app.route('/logout')
def logout():session.clear();return redirect(url_for('login'))
@app.route('/forgot-password',methods=['GET','POST'])
def forgot_password():
    if request.method=='GET':return render_template('forgot_password.html')
    u=request.form.get('username','').strip().lower(); method=request.form.get('method','email'); dest=request.form.get('contact','').strip(); db=get_db(); user=db.execute('SELECT * FROM app_users WHERE username=? AND active=1',(u,)).fetchone()
    if not user: db.close(); return render_template('forgot_password.html',error='We could not verify that account and recovery contact.')
    reg=user['email'] if method=='email' else user['phone']; norm=lambda x:''.join(c for c in str(x) if c.isdigit())
    ok=(dest.lower()==str(reg).lower()) if method=='email' else norm(dest)==norm(reg)
    if not reg or not dest or not ok: db.close(); return render_template('forgot_password.html',error='Recovery contact does not match the saved contact.')
    code=f'{secrets.randbelow(1000000):06d}'; token=secrets.token_urlsafe(32); exp=(datetime.now()+timedelta(minutes=10)).isoformat(timespec='seconds'); db.execute('UPDATE app_users SET reset_code_hash=?,reset_token_hash=?,reset_expires=?,reset_attempts=0 WHERE id=?',(_hash(code),_hash(token),exp,user['id'])); db.commit(); db.close()
    base=os.getenv('PATIENTCARE_BASE_URL','').rstrip('/'); reset_url=(base+url_for('reset_password',token=token,username=u)) if base else url_for('reset_password',token=token,username=u,_external=True); sent,msg=(_send_email(dest,code,reset_url) if method=='email' else _send_sms(dest,code,reset_url)); demo=os.getenv('PATIENTCARE_RESET_DEMO','1')=='1'; demo_code=code if demo and not sent else None
    return render_template('forgot_password.html',message=('Reset code sent to '+(_mask_email(dest) if method=='email' else _mask_phone(dest))) if sent else ('Demo mode: OTP shown below.' if demo else 'Delivery failed: '+msg),demo_code=demo_code,reset_token=token,username=u)
@app.route('/reset-password',methods=['GET','POST'])
def reset_password():
    if request.method=='GET':return render_template('reset_password.html',token=request.args.get('token',''),username=request.args.get('username',''))
    u=request.form.get('username','').strip().lower(); token=request.form.get('token',''); code=request.form.get('code','').strip(); pw=request.form.get('password',''); cp=request.form.get('confirm_password',''); db=get_db(); user=db.execute('SELECT * FROM app_users WHERE username=? AND active=1',(u,)).fetchone(); valid=False
    try: valid=bool(user and user['reset_expires'] and datetime.fromisoformat(user['reset_expires'])>=datetime.now() and user['reset_attempts']<5 and secrets.compare_digest(user['reset_token_hash'] or '',_hash(token)) and secrets.compare_digest(user['reset_code_hash'] or '',_hash(code)))
    except Exception: pass
    if len(pw)<8 or pw!=cp: db.close(); return render_template('reset_password.html',error='Password must be 8+ characters and both fields must match.',token=token,username=u)
    if not valid:
        if user: db.execute('UPDATE app_users SET reset_attempts=COALESCE(reset_attempts,0)+1 WHERE id=?',(user['id'],));db.commit()
        db.close(); return render_template('reset_password.html',error='Invalid or expired reset code.',token=token,username=u)
    db.execute('UPDATE app_users SET password_hash=?,reset_code_hash=NULL,reset_token_hash=NULL,reset_expires=NULL,reset_attempts=0 WHERE id=?',(generate_password_hash(pw),user['id']));db.commit();db.close();return render_template('reset_password.html',success='Password reset successfully. You can now sign in.')
@app.route('/account-security',methods=['GET','POST'])
def account_security():
    if not session.get('logged_in'):return redirect(url_for('login'))
    db=get_db(); u=db.execute('SELECT * FROM app_users WHERE username=?',(session['username'],)).fetchone()
    if request.method=='POST':
        action=request.form.get('action','contact')
        if action=='password':
            current=request.form.get('current_password',''); new=request.form.get('new_password',''); confirm=request.form.get('confirm_password','')
            if not check_password_hash(u['password_hash'],current):
                db.close(); return render_template('account_security.html',error='Current password is incorrect.',user=u)
            if len(new)<10 or new!=confirm:
                db.close(); return render_template('account_security.html',error='New password must be at least 10 characters and both fields must match.',user=u)
            db.execute('UPDATE app_users SET password_hash=? WHERE id=?',(generate_password_hash(new),u['id']));db.commit();audit('Changed account password','account',u['id']);db.close();return render_template('account_security.html',success='Password changed successfully.',user=u)
        email=request.form.get('email','').strip(); phone=request.form.get('phone','').strip()
        if email and len(email)>254 or len(phone)>40:
            db.close();return render_template('account_security.html',error='Please provide a valid email/phone length.',user=u)
        db.execute('UPDATE app_users SET email=?,phone=? WHERE id=?',(email,phone,u['id']));db.commit();u=db.execute('SELECT * FROM app_users WHERE id=?',(u['id'],)).fetchone();audit('Updated recovery contact','account',u['id']);db.close();return render_template('account_security.html',success='Recovery contact updated.',user=u)
    db.close();return render_template('account_security.html',user=u)

# ---- core data ----
def rowdicts(rows):return [dict(r) for r in rows]
@app.get('/api/dashboard')
@login_required
def dashboard():
    if session.get('role') == 'Patient': return jsonify(error='Use the patient portal'), 403
    db=get_db(); today=date.today().isoformat(); role=session.get('role')
    d={'patients':db.execute('SELECT COUNT(*) c FROM patients').fetchone()['c'] if role in ('Administrator','Doctor','Receptionist') else 0,
       'appointments':db.execute("SELECT COUNT(*) c FROM appointments WHERE status!='Cancelled'").fetchone()['c'],
       'records':db.execute('SELECT COUNT(*) c FROM health_records').fetchone()['c'] if role in ('Administrator','Doctor') else 0,
       'screenings':db.execute('SELECT COUNT(*) c FROM ai_screenings').fetchone()['c'] if role in ('Administrator','Doctor') else 0,
       'today_appointments':db.execute("SELECT COUNT(*) c FROM appointments WHERE date=? AND status!='Cancelled'",(today,)).fetchone()['c'],
       'high_risk':db.execute("SELECT COUNT(*) c FROM ai_screenings WHERE risk='High'").fetchone()['c'] if role in ('Administrator','Doctor') else 0,
       'upcoming':db.execute("SELECT COUNT(*) c FROM appointments WHERE date>=? AND status='Scheduled'",(today,)).fetchone()['c'],
       'emergency':db.execute("SELECT COUNT(*) c FROM emergency_cases WHERE status='Open'").fetchone()['c'] if role in ('Administrator','Doctor') else 0,
       'unread_notifications':db.execute('SELECT COUNT(*) c FROM notifications WHERE username=? AND read=0',(session['username'],)).fetchone()['c']}
    db.close();return jsonify(d)
@app.get('/api/patients')
@roles('Administrator','Doctor','Receptionist')
def patients():
    db=get_db(); rows=db.execute('SELECT * FROM patients ORDER BY id DESC').fetchall();db.close();return jsonify(rowdicts(rows))
@app.post('/api/patients')
@roles('Administrator','Doctor','Receptionist')
def add_patient():
    d=request.get_json() or {}; name=str(d.get('name','')).strip()
    if not name:return jsonify(error='Patient name is required'),400
    db=get_db(); c=db.execute('INSERT INTO patients(name,age,gender,phone,email,address,blood_group,allergies,emergency_contact) VALUES(?,?,?,?,?,?,?,?,?)',(name,d.get('age') or None,d.get('gender',''),d.get('phone',''),d.get('email',''),d.get('address',''),d.get('blood_group',''),d.get('allergies',''),d.get('emergency_contact','')));db.commit();pid=c.lastrowid;db.close();audit('Created patient','patient',pid);return jsonify(message='Patient added',id=pid)
@app.put('/api/patients/<int:pid>')
@roles('Administrator','Doctor','Receptionist')
def update_patient(pid):
    d=request.get_json() or {}; name=str(d.get('name','')).strip();
    if not name:return jsonify(error='Patient name is required'),400
    db=get_db();
    if not db.execute('SELECT id FROM patients WHERE id=?',(pid,)).fetchone():db.close();return jsonify(error='Patient not found'),404
    db.execute('UPDATE patients SET name=?,age=?,gender=?,phone=?,email=?,address=?,blood_group=?,allergies=?,emergency_contact=? WHERE id=?',(name,d.get('age') or None,d.get('gender',''),d.get('phone',''),d.get('email',''),d.get('address',''),d.get('blood_group',''),d.get('allergies',''),d.get('emergency_contact',''),pid));db.commit();db.close();audit('Updated patient','patient',pid);return jsonify(message='Patient updated')
@app.delete('/api/patients/<int:pid>')
@roles('Administrator',)
def delete_patient(pid):
    db=get_db();
    if not db.execute('SELECT id FROM patients WHERE id=?',(pid,)).fetchone():db.close();return jsonify(error='Patient not found'),404
    db.execute('DELETE FROM patients WHERE id=?',(pid,));db.commit();db.close();audit('Deleted patient','patient',pid);return jsonify(message='Patient deleted')
@app.get('/api/patients/<int:pid>')
@login_required
def patient_detail(pid):
    if session.get('role') == 'Patient' and session.get('patient_id') != pid: return jsonify(error='You can only access your own patient profile.'),403
    if session.get('role') == 'Receptionist': return jsonify(error='Patient clinical details are restricted to clinical staff.'),403
    db=get_db();p=db.execute('SELECT * FROM patients WHERE id=?',(pid,)).fetchone()
    if not p:db.close();return jsonify(error='Patient not found'),404
    a=db.execute('SELECT a.*,d.specialization FROM appointments a LEFT JOIN doctors d ON a.doctor=d.name WHERE patient_id=? ORDER BY date DESC,time DESC',(pid,)).fetchall()
    if session.get('role') == 'Receptionist':
        # Receptionists can handle demographics and scheduling, but not clinical details.
        safe_patient={k:p[k] for k in ('id','name','age','gender','phone','email','address','emergency_contact','created_at')}
        db.close(); return jsonify(patient=safe_patient,appointments=rowdicts(a),records=[],prescriptions=[],screenings=[],emergencies=[])
    r=db.execute('SELECT * FROM health_records WHERE patient_id=? ORDER BY date DESC,id DESC',(pid,)).fetchall();pr=db.execute('SELECT * FROM prescriptions WHERE patient_id=? ORDER BY date DESC,id DESC',(pid,)).fetchall();s=db.execute('SELECT * FROM ai_screenings WHERE patient_id=? ORDER BY id DESC',(pid,)).fetchall();e=db.execute("SELECT * FROM emergency_cases WHERE patient_id=? ORDER BY id DESC",(pid,)).fetchall();db.close();return jsonify(patient=dict(p),appointments=rowdicts(a),records=rowdicts(r),prescriptions=rowdicts(pr),screenings=rowdicts(s),emergencies=rowdicts(e))

@app.get('/api/doctors')
@roles('Administrator','Doctor','Receptionist')
def get_doctors():db=get_db();r=db.execute('SELECT * FROM doctors WHERE active=1 ORDER BY name').fetchall();db.close();return jsonify(rowdicts(r))
@app.post('/api/doctors')
@roles('Administrator')
def add_doctor():
    d=request.get_json() or {};db=get_db()
    try:c=db.execute('INSERT INTO doctors(name,specialization,phone,email,availability) VALUES(?,?,?,?,?)',(d.get('name','').strip(),d.get('specialization',''),d.get('phone',''),d.get('email',''),d.get('availability','Mon-Fri')));db.commit();i=c.lastrowid
    except Exception as e:db.close();return jsonify(error=str(e)),400
    db.close();audit('Created doctor','doctor',i);return jsonify(message='Doctor added',id=i)
@app.get('/api/appointments')
@roles('Administrator','Doctor','Receptionist')
def get_appointments():db=get_db();r=db.execute('SELECT a.*,p.name patient_name FROM appointments a LEFT JOIN patients p ON a.patient_id=p.id ORDER BY date DESC,time DESC,id DESC').fetchall();db.close();return jsonify(rowdicts(r))
def _conflict(db,doctor,dt,tm,exclude=0):
    return db.execute("SELECT a.id,p.name FROM appointments a LEFT JOIN patients p ON p.id=a.patient_id WHERE a.doctor=? AND a.date=? AND a.time=? AND a.status NOT IN ('Cancelled','Completed') AND a.id!=?",(doctor,dt,tm,exclude)).fetchone()
def _validate_appointment_payload(d):
    if not all(str(d.get(k,'')).strip() for k in ('patient_id','doctor','date','time')):
        return 'Patient, doctor, date and time are required.'
    try:
        int(d['patient_id']); datetime.strptime(str(d['date']),'%Y-%m-%d'); datetime.strptime(str(d['time']),'%H:%M')
    except (ValueError,TypeError): return 'Choose a valid patient, date (YYYY-MM-DD), and time (HH:MM).'
    if d.get('status','Scheduled') not in ('Scheduled','Completed','Cancelled','No-show'): return 'Invalid appointment status.'
    if len(str(d.get('doctor',''))) > 120 or len(str(d.get('reason',''))) > 1000: return 'Doctor or reason field is too long.'
    return None
@app.post('/api/appointments')
@roles('Administrator','Doctor','Receptionist')
def add_appointment():
    d=request.get_json() or {}; err=_validate_appointment_payload(d)
    if err:return jsonify(error=err),400
    db=get_db()
    if not db.execute('SELECT id FROM patients WHERE id=?',(int(d['patient_id']),)).fetchone():db.close();return jsonify(error='Patient not found'),404
    if not db.execute('SELECT id FROM doctors WHERE name=? AND active=1',(str(d['doctor']).strip(),)).fetchone():db.close();return jsonify(error='Choose an active doctor from the directory.'),400
    c=_conflict(db,str(d['doctor']).strip(),d['date'],d['time'])
    if c:db.close();return jsonify(error=f"Doctor conflict: {d['doctor']} already has an appointment at this time."),409
    cur=db.execute('INSERT INTO appointments(patient_id,doctor,date,time,status,reason) VALUES(?,?,?,?,?,?)',(int(d['patient_id']),str(d['doctor']).strip(),d['date'],d['time'],d.get('status','Scheduled'),str(d.get('reason','')).strip()));db.commit();i=cur.lastrowid;db.close();audit('Created appointment','appointment',i);return jsonify(message='Appointment added',id=i),201
@app.put('/api/appointments/<int:aid>')
@roles('Administrator','Doctor','Receptionist')
def update_appointment(aid):
    d=request.get_json() or {}; err=_validate_appointment_payload(d)
    if err:return jsonify(error=err),400
    db=get_db()
    if not db.execute('SELECT id FROM appointments WHERE id=?',(aid,)).fetchone():db.close();return jsonify(error='Appointment not found'),404
    if not db.execute('SELECT id FROM patients WHERE id=?',(int(d['patient_id']),)).fetchone():db.close();return jsonify(error='Patient not found'),404
    if not db.execute('SELECT id FROM doctors WHERE name=? AND active=1',(str(d['doctor']).strip(),)).fetchone():db.close();return jsonify(error='Choose an active doctor from the directory.'),400
    c=_conflict(db,str(d['doctor']).strip(),d['date'],d['time'],aid)
    if c:db.close();return jsonify(error='Doctor conflict detected for this time.'),409
    db.execute('UPDATE appointments SET patient_id=?,doctor=?,date=?,time=?,status=?,reason=? WHERE id=?',(int(d['patient_id']),str(d['doctor']).strip(),d['date'],d['time'],d.get('status','Scheduled'),str(d.get('reason','')).strip(),aid));db.commit();db.close();audit('Updated appointment','appointment',aid);return jsonify(message='Appointment updated')
@app.delete('/api/appointments/<int:aid>')
@roles('Administrator','Receptionist')
def delete_appointment(aid):db=get_db();db.execute('DELETE FROM appointments WHERE id=?',(aid,));db.commit();db.close();audit('Deleted appointment','appointment',aid);return jsonify(message='Appointment deleted')

@app.get('/api/records')
@roles('Administrator','Doctor')
def get_records():db=get_db();r=db.execute('SELECT h.*,p.name patient_name FROM health_records h LEFT JOIN patients p ON p.id=h.patient_id ORDER BY date DESC,id DESC').fetchall();db.close();return jsonify(rowdicts(r))
def _parse_clinical_values(data):
    """Validate optional numeric values without blocking genuinely abnormal readings."""
    specs = {
        'temperature': (25, 45, float), 'heart_rate': (20, 250, int),
        'systolic': (30, 300, int), 'diastolic': (20, 200, int),
        'spo2': (0, 100, float), 'weight': (0.2, 500, float),
        'respiratory_rate': (1, 80, int), 'blood_glucose': (10, 1000, float)
    }
    parsed = {}
    for field, (minimum, maximum, converter) in specs.items():
        raw = data.get(field)
        if raw is None or str(raw).strip() == '':
            parsed[field] = None
            continue
        try:
            value = converter(raw)
        except (TypeError, ValueError):
            return None, f'{field.replace("_", " ").title()} must be numeric.'
        if value < minimum or value > maximum:
            return None, f'{field.replace("_", " ").title()} must be between {minimum} and {maximum}.'
        parsed[field] = value
    if parsed['systolic'] is not None and parsed['diastolic'] is not None and parsed['systolic'] <= parsed['diastolic']:
        return None, 'Systolic blood pressure must be greater than diastolic pressure.'
    return parsed, None

def _vital_alerts(values):
    alerts = []
    if values.get('temperature') is not None and (values['temperature'] >= 38 or values['temperature'] < 35): alerts.append('Temperature outside configured review range')
    if values.get('heart_rate') is not None and (values['heart_rate'] > 100 or values['heart_rate'] < 50): alerts.append('Heart rate outside configured review range')
    if values.get('systolic') is not None and (values['systolic'] >= 140 or values['systolic'] < 90): alerts.append('Systolic blood pressure outside configured review range')
    if values.get('diastolic') is not None and (values['diastolic'] >= 90 or values['diastolic'] < 60): alerts.append('Diastolic blood pressure outside configured review range')
    if values.get('spo2') is not None and values['spo2'] < 94: alerts.append('Low SpO2 reading — prompt clinical review')
    if values.get('respiratory_rate') is not None and (values['respiratory_rate'] > 20 or values['respiratory_rate'] < 12): alerts.append('Respiratory rate outside configured review range')
    return alerts

def _record_values(data):
    values, error = _parse_clinical_values(data)
    if error:
        return None, error
    patient_id = data.get('patient_id')
    try:
        patient_id = int(patient_id)
    except (TypeError, ValueError):
        return None, 'A valid patient_id is required.'
    diagnosis = str(data.get('diagnosis', '')).strip()
    if not diagnosis:
        return None, 'Diagnosis or record title is required.'
    values.update({'patient_id': patient_id, 'diagnosis': diagnosis,
                   'treatment': str(data.get('treatment', '')).strip(),
                   'date': str(data.get('date') or date.today().isoformat()),
                   'notes': str(data.get('notes', '')).strip()})
    try:
        date.fromisoformat(values['date'])
    except ValueError:
        return None, 'Date must use YYYY-MM-DD format.'
    return values, None

@app.post('/api/records')
@roles('Administrator','Doctor')
def add_record():
    d=request.get_json() or {}; values, error = _record_values(d)
    if error: return jsonify(error=error), 400
    db=get_db()
    if not db.execute('SELECT id FROM patients WHERE id=?',(values['patient_id'],)).fetchone(): db.close(); return jsonify(error='Patient not found.'),404
    fields=('patient_id','diagnosis','treatment','date','notes','temperature','heart_rate','systolic','diastolic','spo2','weight','respiratory_rate','blood_glucose')
    cur=db.execute('INSERT INTO health_records('+','.join(fields)+') VALUES('+','.join('?' for _ in fields)+')',tuple(values[k] for k in fields));db.commit();i=cur.lastrowid;db.close();audit('Created health record','record',i)
    alerts=_vital_alerts(values)
    if alerts: notify(session.get('username'),'Vitals need review',f"Patient #{values['patient_id']}: "+'; '.join(alerts),'warning')
    return jsonify(message='Health record added',id=i,alerts=alerts,review_required=bool(alerts)),201

@app.put('/api/records/<int:rid>')
@roles('Administrator','Doctor')
def update_record(rid):
    d=request.get_json() or {}; values, error = _record_values(d)
    if error: return jsonify(error=error), 400
    db=get_db()
    if not db.execute('SELECT id FROM patients WHERE id=?',(values['patient_id'],)).fetchone(): db.close(); return jsonify(error='Patient not found.'),404
    if not db.execute('SELECT id FROM health_records WHERE id=?',(rid,)).fetchone(): db.close(); return jsonify(error='Health record not found.'),404
    fields=('patient_id','diagnosis','treatment','date','notes','temperature','heart_rate','systolic','diastolic','spo2','weight','respiratory_rate','blood_glucose')
    db.execute('UPDATE health_records SET '+','.join(f'{k}=?' for k in fields)+' WHERE id=?',tuple(values[k] for k in fields)+(rid,));db.commit();db.close();audit('Updated health record','record',rid)
    alerts=_vital_alerts(values)
    if alerts: notify(session.get('username'),'Vitals need review',f"Patient #{values['patient_id']}: "+'; '.join(alerts),'warning')
    return jsonify(message='Health record updated',alerts=alerts,review_required=bool(alerts))

# Dedicated vitals API. Vitals are stored in health_records so the existing UI and reports stay in sync.
@app.get('/api/vitals')
@roles('Administrator','Doctor')
def get_vitals():
    db=get_db(); patient_id=request.args.get('patient_id', type=int)
    sql='SELECT h.*, p.name patient_name FROM health_records h LEFT JOIN patients p ON p.id=h.patient_id WHERE (h.temperature IS NOT NULL OR h.heart_rate IS NOT NULL OR h.systolic IS NOT NULL OR h.diastolic IS NOT NULL OR h.spo2 IS NOT NULL OR h.weight IS NOT NULL OR h.respiratory_rate IS NOT NULL OR h.blood_glucose IS NOT NULL)'
    params=()
    if patient_id is not None: sql+=' AND h.patient_id=?'; params=(patient_id,)
    sql+=' ORDER BY h.date DESC,h.id DESC LIMIT 500'; rows=rowdicts(db.execute(sql,params).fetchall()); db.close()
    for item in rows: item['alerts']=_vital_alerts(item); item['review_required']=bool(item['alerts'])
    return jsonify(rows)

@app.post('/api/vitals')
@roles('Administrator','Doctor')
def add_vitals():
    d=request.get_json() or {}; d.setdefault('diagnosis','Vitals Monitoring'); d.setdefault('treatment',''); d.setdefault('notes','Vitals recorded through monitoring form.')
    values, error = _record_values(d)
    if error: return jsonify(error=error),400
    if not any(values.get(k) is not None for k in ('temperature','heart_rate','systolic','diastolic','spo2','weight','respiratory_rate','blood_glucose')):
        return jsonify(error='Enter at least one vital measurement.'),400
    db=get_db()
    if not db.execute('SELECT id FROM patients WHERE id=?',(values['patient_id'],)).fetchone(): db.close(); return jsonify(error='Patient not found.'),404
    fields=('patient_id','diagnosis','treatment','date','notes','temperature','heart_rate','systolic','diastolic','spo2','weight','respiratory_rate','blood_glucose')
    cur=db.execute('INSERT INTO health_records('+','.join(fields)+') VALUES('+','.join('?' for _ in fields)+')',tuple(values[k] for k in fields));db.commit();rid=cur.lastrowid;db.close()
    alerts=_vital_alerts(values); audit('Recorded vitals','patient',values['patient_id'])
    if alerts: notify(session.get('username'),'Vitals need review',f"Patient #{values['patient_id']}: "+'; '.join(alerts),'warning')
    return jsonify(message='Vitals saved',id=rid,alerts=alerts,review_required=bool(alerts)),201

@app.get('/api/patients/<int:pid>/vitals')
@roles('Administrator','Doctor')
def patient_vitals(pid):
    db=get_db()
    if not db.execute('SELECT id FROM patients WHERE id=?',(pid,)).fetchone(): db.close(); return jsonify(error='Patient not found.'),404
    rows=rowdicts(db.execute('SELECT * FROM health_records WHERE patient_id=? AND (temperature IS NOT NULL OR heart_rate IS NOT NULL OR systolic IS NOT NULL OR diastolic IS NOT NULL OR spo2 IS NOT NULL OR weight IS NOT NULL OR respiratory_rate IS NOT NULL OR blood_glucose IS NOT NULL) ORDER BY date DESC,id DESC LIMIT 200',(pid,)).fetchall());db.close()
    for item in rows: item['alerts']=_vital_alerts(item); item['review_required']=bool(item['alerts'])
    return jsonify(rows)

@app.get('/api/patients/<int:pid>/vitals/latest')
@roles('Administrator','Doctor')
def latest_patient_vitals(pid):
    rows=patient_vitals_query(pid)
    if rows is None: return jsonify(error='Patient not found.'),404
    return jsonify(rows[0] if rows else {})

def patient_vitals_query(pid):
    db=get_db()
    if not db.execute('SELECT id FROM patients WHERE id=?',(pid,)).fetchone(): db.close(); return None
    row=db.execute('SELECT * FROM health_records WHERE patient_id=? AND (temperature IS NOT NULL OR heart_rate IS NOT NULL OR systolic IS NOT NULL OR diastolic IS NOT NULL OR spo2 IS NOT NULL OR weight IS NOT NULL OR respiratory_rate IS NOT NULL OR blood_glucose IS NOT NULL) ORDER BY date DESC,id DESC LIMIT 1',(pid,)).fetchone();db.close()
    if not row:return []
    item=dict(row);item['alerts']=_vital_alerts(item);item['review_required']=bool(item['alerts']);return [item]
@app.delete('/api/records/<int:rid>')
@roles('Administrator','Doctor')
def delete_record(rid):db=get_db();db.execute('DELETE FROM health_records WHERE id=?',(rid,));db.commit();db.close();audit('Deleted health record','record',rid);return jsonify(message='Record deleted')

@app.get('/api/prescriptions')
@roles('Administrator','Doctor')
def prescriptions():
    db=get_db();r=db.execute('SELECT p.*,pt.name patient_name FROM prescriptions p LEFT JOIN patients pt ON pt.id=p.patient_id ORDER BY p.date DESC,p.id DESC').fetchall();db.close();return jsonify(rowdicts(r))
@app.post('/api/prescriptions')
@roles('Administrator','Doctor')
def add_prescription():
    d=request.get_json() or {};db=get_db();c=db.execute('INSERT INTO prescriptions(patient_id,doctor,medicine,dosage,frequency,duration,instructions,date,status) VALUES(?,?,?,?,?,?,?,?,?)',(d.get('patient_id'),d.get('doctor') or session.get('username'),d.get('medicine',''),d.get('dosage',''),d.get('frequency',''),d.get('duration',''),d.get('instructions',''),d.get('date') or date.today().isoformat(),d.get('status','Active')));db.commit();i=c.lastrowid;db.close();audit('Created prescription','prescription',i);return jsonify(message='Prescription added',id=i)
@app.delete('/api/prescriptions/<int:pid>')
@roles('Administrator','Doctor')
def delete_prescription(pid):db=get_db();db.execute('DELETE FROM prescriptions WHERE id=?',(pid,));db.commit();db.close();audit('Deleted prescription','prescription',pid);return jsonify(message='Prescription deleted')

# ---- AI, risk and assistant ----
def risk_profile(pid):
    db=get_db();p=db.execute('SELECT * FROM patients WHERE id=?',(pid,)).fetchone(); rows=db.execute('SELECT * FROM health_records WHERE patient_id=? ORDER BY date DESC,id DESC LIMIT 5',(pid,)).fetchall();s=db.execute("SELECT * FROM ai_screenings WHERE patient_id=? ORDER BY id DESC LIMIT 3",(pid,)).fetchall();db.close()
    score=0;f=[]
    if p and p['age'] is not None:
        if p['age']>=65:score+=20;f.append('Age 65+')
        elif p['age']<5:score+=15;f.append('Young age')
    if rows:
        x=rows[0]
        checks=[(x['temperature'] is not None and x['temperature']>=38.0,20,'Elevated temperature'),(x['heart_rate'] is not None and (x['heart_rate']>100 or x['heart_rate']<50),15,'Heart-rate outside demo range'),(x['systolic'] is not None and (x['systolic']>=140 or x['systolic']<90),20,'Systolic BP outside demo range'),(x['spo2'] is not None and x['spo2']<94,30,'Low SpO₂'),(x['blood_glucose'] is not None and (x['blood_glucose']>=200 or x['blood_glucose']<70),15,'Glucose outside demo range')]
        for ok,n,t in checks:
            if ok:score+=n;f.append(t)
    if s and s[0]['risk']=='High':score+=25;f.append('Recent high-risk screening')
    score=min(100,score); level='High' if score>=60 else 'Medium' if score>=30 else 'Low';return {'score':score,'level':level,'factors':f,'patient':dict(p) if p else None,'latest_record':dict(rows[0]) if rows else None}
@app.post('/api/ai/analyze')
@roles('Administrator','Doctor')
def ai_analyze():
    d=request.get_json(silent=True) or {}
    sym=str(d.get('symptoms','')).strip()
    pid=d.get('patient_id') or None
    if not sym:
        return jsonify(error='Enter symptoms before running screening.'),400
    if len(sym)>2000:
        return jsonify(error='Please keep symptom description under 2,000 characters.'),400
    if pid is not None:
        try: pid=int(pid)
        except (TypeError,ValueError): return jsonify(error='Please select a valid patient.'),400
        db=get_db(); exists=db.execute('SELECT id FROM patients WHERE id=?',(pid,)).fetchone(); db.close()
        if not exists: return jsonify(error='Selected patient was not found. Refresh the patient list and try again.'),404
    try:
        result=analyze_symptoms(sym)
        # Symptom screening must still return a result when optional historical risk data is incomplete.
        profile={'score':0,'level':result.get('risk','Low'),'factors':[]}
        if pid:
            try:
                profile=risk_profile(pid)
            except Exception:
                app.logger.exception('Optional patient risk profile could not be calculated; continuing with symptom screening only')
        symptom_score=int(result.get('risk_score',15))
        score=max(symptom_score, int(profile.get('score',0)))
        # Preserve a possible urgent flag from symptom matching; patient profile can raise but not lower risk.
        level='High' if result.get('urgent') or score>=60 else 'Medium' if score>=30 else 'Low'
        factors=list(dict.fromkeys((result.get('factors') or [])+(profile.get('factors') or [])))
        db=get_db()
        try:
            # Run database migrations before inserting, and tolerate older DBs missing newer screening columns.
            cols={row['name'] for row in db.execute('PRAGMA table_info(ai_screenings)').fetchall()}
            migrations={'risk_score':'INTEGER DEFAULT 0','factors':"TEXT DEFAULT ''"}
            for col,decl in migrations.items():
                if col not in cols:
                    db.execute(f'ALTER TABLE ai_screenings ADD COLUMN {col} {decl}')
            c=db.execute('INSERT INTO ai_screenings(patient_id,symptoms,risk,category,recommendation,risk_score,factors,created_at) VALUES(?,?,?,?,?,?,?,?)',
                (pid,sym,level,result.get('category','General'),result.get('recommendation','Review with a healthcare professional.'),score,'; '.join(factors),datetime.now().strftime('%Y-%m-%d %H:%M')))
            db.commit(); i=c.lastrowid
        finally:
            db.close()
        audit('AI screening','ai_screening',i)
        return jsonify(**result,risk=level,risk_score=score,factors=factors,id=i,profile_factors=profile.get('factors',[]))
    except ValueError as exc:
        return jsonify(error=str(exc)),400
    except Exception as exc:
        app.logger.exception('AI screening failed')
        # Keep implementation details in server logs, return a useful safe message to the UI.
        return jsonify(error='Screening failed while saving or calculating the result. Please verify the database schema and server log, then retry.'),500
@app.get('/api/ai/history')
@roles('Administrator','Doctor')
def ai_history():db=get_db();r=db.execute('SELECT a.*,p.name patient_name FROM ai_screenings a LEFT JOIN patients p ON p.id=a.patient_id ORDER BY a.id DESC').fetchall();db.close();return jsonify(rowdicts(r))
@app.get('/api/risk/<int:pid>')
@roles('Administrator','Doctor')
def risk(pid):return jsonify(risk_profile(pid))
@app.get('/api/assistant/<int:pid>')
@roles('Administrator','Doctor')
def assistant(pid):
    q=request.args.get('q','').lower();db=get_db();a=db.execute("SELECT * FROM appointments WHERE patient_id=? ORDER BY date DESC,time DESC LIMIT 5",(pid,)).fetchall();pr=db.execute("SELECT * FROM prescriptions WHERE patient_id=? ORDER BY date DESC LIMIT 5",(pid,)).fetchall();r=db.execute("SELECT * FROM health_records WHERE patient_id=? ORDER BY date DESC LIMIT 1",(pid,)).fetchone();db.close()
    if 'appointment' in q:return jsonify(answer='Latest appointment: '+(f"{a[0]['date']} at {a[0]['time']} with {a[0]['doctor']} ({a[0]['status']})." if a else 'No appointments found.'))
    if 'medicine' in q or 'prescription' in q:return jsonify(answer='Active prescriptions: '+(', '.join(x['medicine']+' '+(x['dosage'] or '') for x in pr if x['status']=='Active') or 'None recorded.'))
    if 'vital' in q or 'health' in q:return jsonify(answer='Latest vitals: '+(f"Temp {r['temperature']}°C, HR {r['heart_rate']} bpm, BP {r['systolic']}/{r['diastolic']}, SpO₂ {r['spo2']}%." if r else 'No vitals recorded.'))
    return jsonify(answer='I can summarize appointments, prescriptions and latest recorded vitals. This assistant is informational and not a diagnosis.')

# ---- emergency/notifications/analytics ----
@app.get('/api/emergency')
@roles('Administrator','Doctor')
def emergency_list():db=get_db();r=db.execute('SELECT e.*,p.name patient_name FROM emergency_cases e LEFT JOIN patients p ON p.id=e.patient_id ORDER BY CASE e.status WHEN "Open" THEN 0 ELSE 1 END,e.id DESC').fetchall();db.close();return jsonify(rowdicts(r))
@app.post('/api/emergency')
@roles('Administrator','Doctor','Receptionist')
def emergency_create():
    d=request.get_json() or {};db=get_db();c=db.execute('INSERT INTO emergency_cases(patient_id,reason,severity,status,notes,created_by) VALUES(?,?,?,?,?,?)',(d.get('patient_id'),d.get('reason',''),d.get('severity','Critical'),'Open',d.get('notes',''),session['username']));db.commit();i=c.lastrowid;db.close();audit('Created emergency case','emergency',i);notify(session['username'],'Emergency case opened',d.get('reason','Critical patient case'),'warning');return jsonify(message='Emergency case created',id=i)
@app.put('/api/emergency/<int:eid>')
@roles('Administrator','Doctor','Receptionist')
def emergency_update(eid):
    d=request.get_json() or {};db=get_db();status=d.get('status','Resolved');db.execute('UPDATE emergency_cases SET status=?,notes=?,resolved_at=? WHERE id=?',(status,d.get('notes',''),datetime.now().isoformat() if status=='Resolved' else None,eid));db.commit();db.close();audit('Updated emergency case','emergency',eid);return jsonify(message='Emergency case updated')
@app.get('/api/notifications')
@login_required
def get_notifications():db=get_db();r=db.execute('SELECT * FROM notifications WHERE username=? ORDER BY id DESC LIMIT 50',(session['username'],)).fetchall();db.close();return jsonify(rowdicts(r))
@app.post('/api/notifications/read')
@login_required
def read_notifications():db=get_db();db.execute('UPDATE notifications SET read=1 WHERE username=?',(session['username'],));db.commit();db.close();return jsonify(message='Notifications marked read')
@app.get('/api/analytics')
@roles('Administrator','Doctor')
def analytics():
    db=get_db();
    def q(sql):return rowdicts(db.execute(sql).fetchall())
    out={'gender':q('SELECT COALESCE(NULLIF(gender,\'\'),\'Unknown\') label,COUNT(*) value FROM patients GROUP BY gender'),'appointments':q('SELECT status label,COUNT(*) value FROM appointments GROUP BY status'),'risk':q('SELECT COALESCE(risk,\'Unknown\') label,COUNT(*) value FROM ai_screenings GROUP BY risk'),'diagnoses':q('SELECT diagnosis label,COUNT(*) value FROM health_records GROUP BY diagnosis ORDER BY value DESC LIMIT 8'),'monthly':q("SELECT substr(date,1,7) label,COUNT(*) value FROM appointments GROUP BY substr(date,1,7) ORDER BY label")};db.close();return jsonify(out)
@app.get('/api/audit')
@roles('Administrator')
def get_audit():db=get_db();r=db.execute('SELECT * FROM audit_logs ORDER BY id DESC LIMIT 200').fetchall();db.close();return jsonify(rowdicts(r))
@app.get('/api/search')
@roles('Administrator','Doctor','Receptionist')
def global_search():
    q=request.args.get('q','').strip().lower();db=get_db();like=f'%{q}%';out=[]
    for r in db.execute('SELECT id,name,phone,email FROM patients WHERE lower(name) LIKE ? OR lower(phone) LIKE ? OR lower(email) LIKE ? LIMIT 10',(like,like,like)).fetchall():out.append({'type':'Patient','id':r['id'],'title':r['name'],'meta':r['phone'] or r['email'] or ''})
    for r in db.execute('SELECT id,name,specialization FROM doctors WHERE lower(name) LIKE ? OR lower(specialization) LIKE ? LIMIT 10',(like,like)).fetchall():out.append({'type':'Doctor','id':r['id'],'title':r['name'],'meta':r['specialization']})
    for r in db.execute('SELECT p.id,p.name,a.date,a.time FROM appointments a JOIN patients p ON p.id=a.patient_id WHERE lower(p.name) LIKE ? OR lower(a.doctor) LIKE ? LIMIT 10',(like,like)).fetchall():out.append({'type':'Appointment','id':r['id'],'title':r['name'],'meta':f"{r['date']} {r['time']}"})
    db.close();return jsonify(out[:20])


# ---- enhanced clinical workflows ----
@app.get('/api/medications')
@roles('Administrator','Doctor')
def get_medications():
    db=get_db(); rows=db.execute('SELECT * FROM medications WHERE active=1 ORDER BY name').fetchall(); db.close(); return jsonify(rowdicts(rows))

@app.get('/api/timeline/<int:pid>')
@roles('Administrator','Doctor')
def patient_timeline(pid):
    """Return a unified, date-descending timeline for an authorized clinical user."""
    db=get_db()
    p=db.execute('SELECT * FROM patients WHERE id=?',(pid,)).fetchone()
    if not p:
        db.close()
        return jsonify(error='Patient not found'),404
    events=[]
    for r in db.execute('SELECT id,date,diagnosis,treatment,notes,temperature,heart_rate,systolic,diastolic,spo2,weight,respiratory_rate,blood_glucose FROM health_records WHERE patient_id=? ORDER BY date DESC,id DESC',(pid,)).fetchall():
        vitals=[]
        for label,key,unit in [('Temperature','temperature','°C'),('Heart rate','heart_rate','bpm'),('Blood pressure','systolic','') ,('SpO₂','spo2','%'),('Weight','weight','kg'),('Respiratory rate','respiratory_rate','/min'),('Blood glucose','blood_glucose','')]:
            value=r[key]
            if value is not None:
                if key=='systolic':
                    value=f"{value}/{r['diastolic'] if r['diastolic'] is not None else '—'}"
                elif key=='diastolic':
                    continue
                vitals.append(f'{label}: {value}{unit}')
        events.append({'date':r['date'],'type':'Health Record','title':r['diagnosis'] or 'Clinical record','details':' · '.join(x for x in [r['treatment'],r['notes']] if x) or 'No additional details recorded.','id':r['id']})
        if vitals:
            events.append({'date':r['date'],'type':'Vital Signs','title':'Recorded vital signs','details':' · '.join(vitals),'id':r['id']})
    for r in db.execute('SELECT id,date,time,doctor,status,reason FROM appointments WHERE patient_id=? ORDER BY date DESC,time DESC',(pid,)).fetchall():
        events.append({'date':r['date'],'time':r['time'],'type':'Appointment','title':f"{r['doctor']} · {r['status']}",'details':r['reason'] or 'No reason recorded.','id':r['id']})
    for r in db.execute('SELECT id,date,medicine,dosage,frequency,duration,status,instructions,doctor FROM prescriptions WHERE patient_id=? ORDER BY date DESC,id DESC',(pid,)).fetchall():
        events.append({'date':r['date'],'type':'Prescription','title':f"{r['medicine']} · {r['status']}",'details':' · '.join(x for x in [r['dosage'],r['frequency'],r['duration'],r['instructions'],('Prescribed by '+r['doctor']) if r['doctor'] else ''] if x),'id':r['id']})
    for r in db.execute('SELECT id,substr(created_at,1,10) date,risk,category,risk_score,recommendation,symptoms FROM ai_screenings WHERE patient_id=? ORDER BY id DESC',(pid,)).fetchall():
        events.append({'date':r['date'],'type':'AI Screening','title':f"{r['risk']} risk · {r['category']}",'details':f"Score {r['risk_score']}/100 · Symptoms: {r['symptoms']} · {r['recommendation']}",'id':r['id']})
    for r in db.execute('SELECT id,substr(created_at,1,10) date,reason,severity,status,notes FROM emergency_cases WHERE patient_id=? ORDER BY id DESC',(pid,)).fetchall():
        events.append({'date':r['date'],'type':'Emergency','title':f"{r['severity']} · {r['status']}",'details':' · '.join(x for x in [r['reason'],r['notes']] if x),'id':r['id']})
    db.close()
    events.sort(key=lambda x:((x.get('date') or ''),(x.get('time') or '')),reverse=True)
    audit('Viewed patient health timeline','patient',pid)
    return jsonify(patient=dict(p),events=events)

@app.get('/api/doctor-dashboard')
@roles('Administrator','Doctor')
def doctor_dashboard():
    db=get_db(); today=date.today().isoformat();
    d={
      'today':rowdicts(db.execute("SELECT a.*,p.name patient_name FROM appointments a LEFT JOIN patients p ON p.id=a.patient_id WHERE a.date=? ORDER BY a.time",(today,)).fetchall()),
      'pending':db.execute("SELECT COUNT(*) c FROM appointments WHERE status='Scheduled' AND date>=?",(today,)).fetchone()['c'],
      'critical':db.execute("SELECT COUNT(*) c FROM emergency_cases WHERE status='Open' AND severity IN ('Critical','High')").fetchone()['c'],
      'high_risk':db.execute("SELECT COUNT(*) c FROM ai_screenings WHERE risk='High'").fetchone()['c'],
      'records_today':db.execute("SELECT COUNT(*) c FROM health_records WHERE date=?",(today,)).fetchone()['c']}
    db.close(); return jsonify(d)

@app.get('/api/patient-portal')
@roles('Patient')
def patient_portal():
    pid=session.get('patient_id')
    if not pid:return jsonify(error='No patient profile is linked to this account'),404
    db=get_db(); p=db.execute('SELECT * FROM patients WHERE id=?',(pid,)).fetchone()
    a=db.execute('SELECT * FROM appointments WHERE patient_id=? ORDER BY date DESC,time DESC',(pid,)).fetchall()
    r=db.execute('SELECT * FROM health_records WHERE patient_id=? ORDER BY date DESC,id DESC LIMIT 20',(pid,)).fetchall()
    pr=db.execute('SELECT * FROM prescriptions WHERE patient_id=? ORDER BY date DESC,id DESC LIMIT 20',(pid,)).fetchall()
    s=db.execute('SELECT * FROM ai_screenings WHERE patient_id=? ORDER BY id DESC LIMIT 20',(pid,)).fetchall()
    labs=db.execute('SELECT id,title,file_name,uploaded_at FROM lab_reports WHERE patient_id=? ORDER BY id DESC LIMIT 20',(pid,)).fetchall()
    db.close(); return jsonify(patient=dict(p),appointments=rowdicts(a),records=rowdicts(r),prescriptions=rowdicts(pr),screenings=rowdicts(s),lab_reports=rowdicts(labs))

@app.post('/api/appointments/<int:aid>/remind')
@roles('Administrator','Doctor','Receptionist')
def appointment_reminder(aid):
    d=request.get_json(silent=True) or {}; channel=str(d.get('channel','in-app')).lower()
    if channel not in ('in-app','email','sms'):return jsonify(error='Channel must be in-app, email, or sms.'),400
    db=get_db(); row=db.execute('SELECT a.*,p.name patient_name,p.email patient_email,p.phone patient_phone FROM appointments a LEFT JOIN patients p ON p.id=a.patient_id WHERE a.id=?',(aid,)).fetchone()
    if not row: db.close(); return jsonify(error='Appointment not found'),404
    msg=f"Appointment reminder: {row['patient_name']} has an appointment with {row['doctor']} on {row['date']} at {row['time']}."
    users=db.execute('SELECT username FROM app_users WHERE patient_id=? AND active=1',(row['patient_id'],)).fetchall()
    for user in users: db.execute('INSERT INTO notifications(username,title,message,kind) VALUES(?,?,?,?)',(user['username'],'Appointment Reminder',msg,'info'))
    status='queued';detail=f'In-app reminder queued for {len(users)} linked account(s).'
    if channel=='email':
        if not row['patient_email']:status='no-contact';detail='No email address is recorded for this patient.'
        else:
            sent,reason=_send_notice_email(row['patient_email'],'Suraksha Health Care appointment reminder',msg);status='sent' if sent else ('not-configured' if 'not configured' in reason else 'failed');detail='Email reminder sent.' if sent else 'Email reminder not sent: '+reason
    elif channel=='sms':
        if not row['patient_phone']:status='no-contact';detail='No phone number is recorded for this patient.'
        else:
            sent,reason=_send_notice_sms(row['patient_phone'],msg);status='sent' if sent else ('not-configured' if 'not configured' in reason else 'failed');detail='SMS reminder sent.' if sent else 'SMS reminder not sent: '+reason
    db.execute('INSERT INTO appointment_reminders(appointment_id,channel,status,message) VALUES(?,?,?,?)',(aid,channel,status,msg));db.execute('UPDATE appointments SET reminder_sent=1 WHERE id=?',(aid,));db.commit();db.close();audit('Queued appointment reminder','appointment',aid,details=f'{channel}: {status}; {detail}')
    return jsonify(message=detail,recipient_count=len(users),channel=channel,status=status)

# ---- reports ----
def _patient_report_data(pid):
    db=get_db()
    p=db.execute('SELECT * FROM patients WHERE id=?',(pid,)).fetchone()
    a=db.execute('SELECT * FROM appointments WHERE patient_id=? ORDER BY date DESC,time DESC',(pid,)).fetchall()
    r=db.execute('SELECT * FROM health_records WHERE patient_id=? ORDER BY date DESC,id DESC',(pid,)).fetchall()
    pr=db.execute('SELECT * FROM prescriptions WHERE patient_id=? ORDER BY date DESC,id DESC',(pid,)).fetchall()
    s=db.execute('SELECT * FROM ai_screenings WHERE patient_id=? ORDER BY id DESC',(pid,)).fetchall()
    db.close()
    return p,a,r,pr,s

@app.get('/api/reports/patient/<int:pid>')
@roles('Administrator','Doctor')
def patient_report(pid):
    if session.get('role') == 'Patient' and session.get('patient_id') != pid:
        return jsonify(error='You can only access your own report.'),403
    p,a,r,pr,s=_patient_report_data(pid)
    if not p:
        return jsonify(error='Patient not found'),404
    try:
        from xml.sax.saxutils import escape
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
            TableStyle, KeepTogether, Flowable, HRFlowable, Image as RLImage)

        # All user/database text is escaped before being put into ReportLab Paragraph markup.
        def safe(value, fallback='—'):
            if value is None or str(value).strip() == '': return fallback
            return escape(str(value))
        def para(value, style='Cell'):
            return Paragraph(safe(value), styles[style])
        def cell(value, fallback='—'):
            return Paragraph(safe(value, fallback), styles['Cell'])

        navy=colors.HexColor('#123B5D'); blue=colors.HexColor('#1677C8')
        pale=colors.HexColor('#EAF5FC'); teal=colors.HexColor('#0F9D91')
        ink=colors.HexColor('#243746'); muted=colors.HexColor('#607586')
        line=colors.HexColor('#D7E5EF'); soft=colors.HexColor('#F6FAFD')
        alert=colors.HexColor('#FFF1E8'); white=colors.white
        styles=getSampleStyleSheet()
        styles.add(ParagraphStyle(name='ReportTitle', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=21, leading=25, textColor=navy, alignment=TA_LEFT, spaceAfter=2))
        styles.add(ParagraphStyle(name='Subtitle', parent=styles['Normal'], fontSize=9, leading=13, textColor=muted))
        styles.add(ParagraphStyle(name='Section', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=navy, spaceBefore=8, spaceAfter=6, keepWithNext=True))
        styles.add(ParagraphStyle(name='Cell', parent=styles['BodyText'], fontName='Helvetica', fontSize=7.5, leading=10, textColor=ink, wordWrap='CJK'))
        styles.add(ParagraphStyle(name='CellHead', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=7.2, leading=9, textColor=white))
        styles.add(ParagraphStyle(name='SmallMuted', parent=styles['BodyText'], fontSize=7.5, leading=10, textColor=muted))
        styles.add(ParagraphStyle(name='CardLabel', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=7, leading=9, textColor=muted))
        styles.add(ParagraphStyle(name='CardValue', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=navy))
        styles.add(ParagraphStyle(name='Note', parent=styles['BodyText'], fontSize=7.5, leading=10, textColor=muted))
        styles.add(ParagraphStyle(name='AIBadge', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=8, leading=11, textColor=blue))

        class AIDoctorPortrait(Flowable):
            """Small vector AI-doctor illustration; no external images/network needed."""
            def __init__(self, width=34*mm, height=34*mm):
                super().__init__(); self.width=width; self.height=height
            def draw(self):
                c=self.canv; w=self.width; h=self.height
                c.saveState()
                c.setFillColor(pale); c.circle(w/2,h/2,min(w,h)*.47,stroke=0,fill=1)
                # shoulders and white coat
                c.setFillColor(colors.HexColor('#2B78B8')); c.roundRect(w*.19,h*.08,w*.62,h*.38,5,stroke=0,fill=1)
                c.setFillColor(white); path=c.beginPath(); path.moveTo(w*.34,h*.42); path.lineTo(w*.5,h*.18); path.lineTo(w*.66,h*.42); path.lineTo(w*.59,h*.48); path.lineTo(w*.41,h*.48); path.close(); c.drawPath(path,stroke=0,fill=1)
                # neck and face
                c.setFillColor(colors.HexColor('#C98762')); c.roundRect(w*.43,h*.39,w*.14,h*.18,3,stroke=0,fill=1)
                c.setFillColor(colors.HexColor('#D99A74')); c.ellipse(w*.31,h*.43,w*.69,h*.82,stroke=0,fill=1)
                # hair cap and side hair
                c.setFillColor(colors.HexColor('#24344D')); c.wedge(w*.29,h*.61,w*.71,h*.87,0,180,stroke=0,fill=1)
                c.setFillColor(colors.HexColor('#24344D')); c.ellipse(w*.28,h*.56,w*.37,h*.77,stroke=0,fill=1); c.ellipse(w*.63,h*.56,w*.72,h*.77,stroke=0,fill=1)
                # face details
                c.setFillColor(navy); c.circle(w*.43,h*.64,1.1,stroke=0,fill=1); c.circle(w*.57,h*.64,1.1,stroke=0,fill=1)
                c.setStrokeColor(colors.HexColor('#9A5747')); c.setLineWidth(.8); c.arc(w*.43,h*.52,w*.57,h*.60,200,140)
                # stethoscope
                c.setStrokeColor(teal); c.setLineWidth(1.7); c.line(w*.39,h*.42,w*.39,h*.31); c.line(w*.39,h*.31,w*.5,h*.27); c.line(w*.5,h*.27,w*.61,h*.31); c.line(w*.61,h*.31,w*.61,h*.38); c.setFillColor(teal); c.circle(w*.61,h*.38,2,stroke=0,fill=1)
                c.restoreState()

        def section_title(title):
            return Table([[Paragraph(safe(title),styles['Section'])]], colWidths=[180*mm], style=TableStyle([
                ('BACKGROUND',(0,0),(-1,-1),pale),('BOX',(0,0),(-1,-1),.4,line),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),1),('BOTTOMPADDING',(0,0),(-1,-1),-2)]))

        def data_table(headers, rows, widths):
            data=[[Paragraph(safe(h),styles['CellHead']) for h in headers]]
            if rows:
                for row in rows: data.append([cell(v) for v in row])
            else:
                data.append([Paragraph('No entries recorded for this section.',styles['SmallMuted'])]+[Paragraph('',styles['Cell']) for _ in headers[1:]])
            t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
            t.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),navy),('TEXTCOLOR',(0,0),(-1,0),white),
                ('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.35,line),
                ('ROWBACKGROUNDS',(0,1),(-1,-1),[white,soft]),
                ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
                ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
            ]))
            if not rows: t.setStyle(TableStyle([('SPAN',(0,1),(-1,1))]))
            return t

        now=datetime.now().strftime('%d %b %Y, %I:%M %p')
        buf=io.BytesIO()
        doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=15*mm,leftMargin=15*mm,topMargin=24*mm,bottomMargin=17*mm,title=f"Suraksha Health Care Patient Report - {p['name']}",author='Suraksha Health Care Patient Care Management System')
        story=[]
        brand=Table([[Paragraph('<font size="21" color="#1677C8"><b>✚ Suraksha Health Care</b></font><br/><font size="8" color="#607586">PATIENT CARE MANAGEMENT SYSTEM · PRJ_279</font>',styles['Normal']),Paragraph('<b>PATIENT HEALTH REPORT</b><br/><font size="8" color="#607586">Complete health summary · Confidential</font>',ParagraphStyle('ReportRight',parent=styles['Normal'],alignment=TA_RIGHT,textColor=navy,fontSize=12,leading=16))]],colWidths=[95*mm,85*mm])
        brand.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),pale),('BOX',(0,0),(-1,-1),.7,line),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10)]))
        story += [brand,Spacer(1,5*mm)]

        # Use a bundled AI-doctor illustration in the PDF; no network access required.
        portrait_path=os.path.join(app.root_path, 'static', 'ai_doctor.png')
        portrait=RLImage(portrait_path, width=34*mm, height=37*mm) if os.path.exists(portrait_path) else AIDoctorPortrait()
        identity=Table([
            [Paragraph('PATIENT PROFILE',styles['CardLabel']),'',portrait],
            [Paragraph(safe(p['name']),styles['ReportTitle']),'',Paragraph('<b>Suraksha Health Care AI Health Assistant</b><br/><font size="7" color="#607586">Illustrative digital assistant · not a clinician</font>',styles['Cell'])],
            [Paragraph(f"Patient ID: {p['id']}",styles['Cell']),Paragraph(f"Age: {safe(p['age'])}  |  Gender: {safe(p['gender'])}",styles['Cell']),''],
            [Paragraph(f"Blood group: {safe(p['blood_group'])}",styles['Cell']),Paragraph(f"Phone: {safe(p['phone'])}",styles['Cell']),''],
            [Paragraph(f"Email: {safe(p['email'])}",styles['Cell']),Paragraph(f"Address: {safe(p['address'])}",styles['Cell']),''],
        ],colWidths=[61*mm,65*mm,54*mm])
        identity.setStyle(TableStyle([('SPAN',(0,0),(1,0)),('SPAN',(2,0),(2,1)),('SPAN',(0,1),(1,1)),('SPAN',(0,4),(1,4)),('BACKGROUND',(0,0),(-1,-1),soft),('BOX',(0,0),(-1,-1),.6,line),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
        story += [identity,Spacer(1,3*mm)]
        allergy_text=safe(p['allergies'],'No allergies recorded')
        allergy=Table([[Paragraph('<b>ALLERGY / SAFETY NOTE</b>',styles['Cell']),Paragraph(allergy_text,styles['Cell'])]],colWidths=[42*mm,138*mm])
        allergy.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),alert if p['allergies'] and str(p['allergies']).strip().lower() not in ('none','none known','n/a') else pale),('BOX',(0,0),(-1,-1),.5,line),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
        story += [allergy,Spacer(1,3*mm)]

        # Snapshot cards
        metrics=[('APPOINTMENTS',len(a)),('HEALTH RECORDS',len(r)),('PRESCRIPTIONS',len(pr)),('AI SCREENINGS',len(s))]
        cards=[]
        for label,value in metrics:
            cards.append(Table([[Paragraph(label,styles['CardLabel'])],[Paragraph(str(value),styles['CardValue'])]],colWidths=[42*mm],style=TableStyle([('BACKGROUND',(0,0),(-1,-1),pale),('BOX',(0,0),(-1,-1),.5,line),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)])))
        summary=Table([cards],colWidths=[45*mm]*4)
        summary.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),1),('RIGHTPADDING',(0,0),(-1,-1),1)]))
        story += [summary,Spacer(1,2*mm)]

        story += [section_title('Health Records & Vital Signs'),Spacer(1,2*mm)]
        health_rows=[]
        for x in r:
            vitals=[]
            if x['temperature'] is not None: vitals.append(f"Temp {safe(x['temperature'])} °C")
            if x['heart_rate'] is not None: vitals.append(f"HR {safe(x['heart_rate'])} bpm")
            if x['systolic'] is not None or x['diastolic'] is not None: vitals.append(f"BP {safe(x['systolic'])}/{safe(x['diastolic'])} mmHg")
            if x['spo2'] is not None: vitals.append(f"SpO₂ {safe(x['spo2'])}%")
            if x['weight'] is not None: vitals.append(f"Weight {safe(x['weight'])} kg")
            health_rows.append([x['date'],x['diagnosis'],x['treatment'],', '.join(vitals) or 'Not recorded'])
        story += [data_table(['Date','Diagnosis / Record','Treatment / Plan','Recorded Vitals'],health_rows,[25*mm,42*mm,47*mm,66*mm]),Spacer(1,3*mm)]

        story += [section_title('Appointments'),Spacer(1,2*mm)]
        story += [data_table(['Date','Time','Doctor','Status','Reason'],[[x['date'],x['time'],x['doctor'],x['status'],x['reason']] for x in a],[27*mm,20*mm,43*mm,28*mm,62*mm]),Spacer(1,3*mm)]

        story += [section_title('Prescriptions'),Spacer(1,2*mm)]
        story += [data_table(['Date','Medicine','Dosage','Frequency','Duration / Status'],[[x['date'],x['medicine'],x['dosage'],x['frequency'],f"{x['duration'] or '—'} / {x['status'] or '—'}"] for x in pr],[25*mm,40*mm,30*mm,35*mm,50*mm]),Spacer(1,3*mm)]

        story += [section_title('AI-Assisted Screening History'),Spacer(1,2*mm)]
        story += [data_table(['Date','Risk','Category','Score','Symptoms / Notes'],[[x['created_at'],x['risk'],x['category'],x['risk_score'],x['symptoms']] for x in s],[31*mm,23*mm,32*mm,18*mm,76*mm]),Spacer(1,3*mm)]
        story += [Table([[Paragraph('<b>Important:</b> AI screening results are educational decision-support information only and are not a diagnosis. This report summarizes information recorded in Suraksha Health Care; missing or outdated records may not be shown. Consult a qualified healthcare professional for medical decisions.',styles['Note'])]],colWidths=[180*mm],style=TableStyle([('BACKGROUND',(0,0),(-1,-1),soft),('BOX',(0,0),(-1,-1),.5,line),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)])),Spacer(1,4*mm),Paragraph(f"Generated on {safe(now)} · Suraksha Health Care PRJ_279 · For authorized care-team use",styles['SmallMuted'])]

        def page_decor(canvas, document):
            canvas.saveState(); w,h=A4
            canvas.setFillColor(blue); canvas.rect(0,h-5*mm,w,5*mm,stroke=0,fill=1)
            canvas.setFillColor(colors.HexColor('#EAF5FC')); canvas.rect(0,0,w,2.5*mm,stroke=0,fill=1)
            canvas.setStrokeColor(line); canvas.line(15*mm,12*mm,w-15*mm,12*mm)
            canvas.setFont('Helvetica',7); canvas.setFillColor(muted)
            canvas.drawString(15*mm,7*mm,'Suraksha Health Care · Confidential patient information')
            canvas.drawRightString(w-15*mm,7*mm,f'Page {document.page}')
            canvas.restoreState()
        doc.build(story,onFirstPage=page_decor,onLaterPages=page_decor)
        buf.seek(0); audit('Generated patient report','patient',pid)
        return send_file(buf,as_attachment=True,download_name=f'Suraksha Health Care_patient_{pid}_report.pdf',mimetype='application/pdf')
    except ImportError:
        return jsonify(error='Install reportlab to generate PDF reports.'),500


# ---- competition upgrade: inventory, lab reports, QR, backups, demo data ----
@app.get('/api/inventory')
@roles('Administrator','Doctor')
def inventory_list():
    db=get_db(); rows=db.execute("SELECT *, CASE WHEN expiry_date < date('now') THEN 'Expired' WHEN expiry_date <= date('now','+60 days') THEN 'Expiring soon' WHEN quantity <= 10 THEN 'Low stock' ELSE 'In stock' END AS stock_status FROM medicine_inventory ORDER BY expiry_date ASC").fetchall(); db.close(); return jsonify(rowdicts(rows))

@app.post('/api/inventory')
@roles('Administrator')
def inventory_add():
    d=request.get_json() or {}; medicine=str(d.get('medicine','')).strip(); expiry=str(d.get('expiry_date','')).strip()
    try: qty=int(d.get('quantity',0))
    except (ValueError,TypeError): return jsonify(error='Quantity must be a whole number'),400
    if not medicine or not expiry or qty<0: return jsonify(error='Medicine, valid expiry date, and non-negative quantity are required'),400
    try: datetime.strptime(expiry,'%Y-%m-%d')
    except ValueError: return jsonify(error='Expiry date must use YYYY-MM-DD'),400
    db=get_db(); cur=db.execute('INSERT INTO medicine_inventory(medicine,batch_number,quantity,expiry_date,supplier) VALUES(?,?,?,?,?)',(medicine,d.get('batch_number',''),qty,expiry,d.get('supplier',''))); db.commit(); iid=cur.lastrowid; db.close(); audit('Added medicine inventory','inventory',iid); return jsonify(message='Inventory item added',id=iid)

@app.put('/api/inventory/<int:iid>')
@roles('Administrator')
def inventory_update(iid):
    d=request.get_json() or {}
    try: qty=int(d.get('quantity',0)); datetime.strptime(str(d.get('expiry_date','')),'%Y-%m-%d')
    except (ValueError,TypeError): return jsonify(error='Enter a valid quantity and expiry date'),400
    if qty<0 or not str(d.get('medicine','')).strip(): return jsonify(error='Medicine and non-negative quantity are required'),400
    db=get_db(); cur=db.execute('UPDATE medicine_inventory SET medicine=?,batch_number=?,quantity=?,expiry_date=?,supplier=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(d['medicine'].strip(),d.get('batch_number',''),qty,d['expiry_date'],d.get('supplier',''),iid)); db.commit(); db.close()
    if not cur.rowcount:return jsonify(error='Inventory item not found'),404
    audit('Updated medicine inventory','inventory',iid); return jsonify(message='Inventory updated')

@app.delete('/api/inventory/<int:iid>')
@roles('Administrator')
def inventory_delete(iid):
    db=get_db(); cur=db.execute('DELETE FROM medicine_inventory WHERE id=?',(iid,)); db.commit(); db.close()
    if not cur.rowcount:return jsonify(error='Inventory item not found'),404
    audit('Deleted medicine inventory','inventory',iid); return jsonify(message='Inventory item deleted')

@app.get('/api/labs')
@roles('Administrator','Doctor')
def lab_list():
    db=get_db(); rows=db.execute('SELECT l.*,p.name patient_name FROM lab_reports l JOIN patients p ON p.id=l.patient_id ORDER BY l.id DESC').fetchall(); db.close(); return jsonify(rowdicts(rows))

@app.post('/api/labs')
@roles('Administrator','Doctor')
def lab_upload():
    patient_id=request.form.get('patient_id',''); title=request.form.get('title','').strip(); file=request.files.get('file')
    if not patient_id.isdigit() or not title or not file or not file.filename:return jsonify(error='Patient, report title, and file are required'),400
    ext=os.path.splitext(file.filename)[1].lower()
    if ext not in {'.pdf','.png','.jpg','.jpeg'}:return jsonify(error='Only PDF, PNG, JPG, and JPEG files are allowed'),400
    db=get_db(); patient=db.execute('SELECT id FROM patients WHERE id=?',(int(patient_id),)).fetchone(); db.close()
    if not patient:return jsonify(error='Patient not found'),404
    import uuid
    folder=os.path.join(app.root_path,'private_uploads','labs'); os.makedirs(folder,exist_ok=True); stored=uuid.uuid4().hex+ext; file.save(os.path.join(folder,stored))
    db=get_db(); cur=db.execute('INSERT INTO lab_reports(patient_id,title,file_name,stored_name,uploaded_by) VALUES(?,?,?,?,?)',(int(patient_id),title,os.path.basename(file.filename),stored,session.get('username'))); db.commit(); rid=cur.lastrowid; db.close(); audit('Uploaded lab report','lab_report',rid)
    return jsonify(message='Lab report uploaded',id=rid,url=url_for('lab_download',rid=rid)),201

@app.get('/api/labs/<int:rid>/download')
@login_required
def lab_download(rid):
    role=session.get('role')
    db=get_db(); row=db.execute('SELECT * FROM lab_reports WHERE id=?',(rid,)).fetchone(); db.close()
    if not row: abort(404)
    if role=='Patient' and row['patient_id']!=session.get('patient_id'): abort(403)
    if role not in ('Administrator','Doctor','Patient'): abort(403)
    path=os.path.join(app.root_path,'private_uploads','labs',os.path.basename(row['stored_name']))
    if not os.path.isfile(path):abort(404)
    return send_file(path,as_attachment=True,download_name=row['file_name'])

@app.get('/patient-card/<token>')
def patient_card(token):
    """QR landing page with limited identification details; clinical records require login."""
    from itsdangerous import URLSafeSerializer, BadSignature
    from markupsafe import escape
    serializer = URLSafeSerializer(app.secret_key, salt='suraksha-patient-qr-v1')
    try:
        data = serializer.loads(token)
        pid = int(data.get('pid'))
    except (BadSignature, TypeError, ValueError, AttributeError):
        return '<h1>Invalid patient QR code</h1><p>Please ask authorized staff to generate a new code.</p>', 400
    db=get_db(); row=db.execute('SELECT id,name,age,gender,blood_group FROM patients WHERE id=?',(pid,)).fetchone(); db.close()
    if not row: return '<h1>Patient record not found</h1>',404
    name=escape(row['name'] or 'Not recorded')
    age=escape(str(row['age']) if row['age'] is not None else 'Not recorded')
    gender=escape(row['gender'] or 'Not recorded')
    blood=escape(row['blood_group'] or 'Not recorded')
    page = ('<!doctype html><html lang="en"><meta name="viewport" content="width=device-width,initial-scale=1">'
      '<title>Suraksha Health Care - Patient Card</title><body style="font:16px Arial;background:#eaf2ff;color:#12304a;margin:0;padding:24px">'
      '<main style="max-width:560px;margin:5vh auto;background:white;border-radius:18px;padding:26px;box-shadow:0 12px 35px #12304a20">'
      '<h1 style="color:#174b87">Suraksha Health Care</h1><p>Patient identification card</p><hr>'
      f'<h2>{name}</h2><p><b>Patient ID:</b> {pid}</p><p><b>Age:</b> {age}</p><p><b>Gender:</b> {gender}</p><p><b>Blood group:</b> {blood}</p>'
      '<p style="color:#9a3412">For identification only. Verify identity before care. Confidential medical records are not shown on this QR page.</p>'
      '<a href="/login" style="display:inline-block;padding:12px 18px;background:#174b87;color:white;border-radius:9px;text-decoration:none">Sign in to view authorized records</a>'
      '</main></body></html>')
    return page

@app.get('/api/patients/<int:pid>/qr')
@login_required
def patient_qr(pid):
    role=session.get('role')
    if role not in ('Administrator','Doctor','Receptionist','Patient'): return jsonify(error='Permission denied'),403
    if role=='Patient' and session.get('patient_id')!=pid: return jsonify(error='You can only access your own profile'),403
    db=get_db(); row=db.execute('SELECT id FROM patients WHERE id=?',(pid,)).fetchone(); db.close()
    if not row: return jsonify(error='Patient not found'),404
    try:
        import qrcode
        from itsdangerous import URLSafeSerializer
        # For a phone scan, use the computer's LAN address or set SURAKSHA_PUBLIC_BASE_URL.
        base=os.getenv('SURAKSHA_PUBLIC_BASE_URL','').strip().rstrip('/') or request.host_url.rstrip('/')
        token=URLSafeSerializer(app.secret_key, salt='suraksha-patient-qr-v1').dumps({'pid':pid})
        payload=f'{base}/patient-card/{token}'
        img=qrcode.make(payload); buf=io.BytesIO(); img.save(buf,format='PNG'); buf.seek(0)
        return send_file(buf,mimetype='image/png',download_name=f'Suraksha_Health_Care_patient_{pid}_QR.png')
    except ImportError: return jsonify(error='QR support requires qrcode[pil]. Install project requirements and restart.'),500

@app.get('/api/admin/backup')
@roles('Administrator')
def database_backup():
    db=get_db(); db.execute('PRAGMA wal_checkpoint(FULL)'); db.close()
    path=os.path.join(os.path.dirname(__file__),'patientcare.db')
    src=sqlite3.connect(path); dst=sqlite3.connect(':memory:'); src.backup(dst); raw=dst.serialize(); dst.close(); src.close()
    audit('Downloaded database backup','database')
    return send_file(io.BytesIO(raw),as_attachment=True,download_name='caresphere_backup.db',mimetype='application/octet-stream')

@app.post('/api/admin/restore')
@roles('Administrator')
def database_restore():
    upload=request.files.get('database')
    if not upload or not upload.filename:return jsonify(error='Choose a .db backup file'),400
    if not upload.filename.lower().endswith(('.db','.sqlite','.sqlite3')):return jsonify(error='Backup must be a SQLite .db/.sqlite file'),400
    import tempfile
    base=os.path.dirname(__file__); fd,tmp=tempfile.mkstemp(prefix='caresphere_restore_',suffix='.db',dir=base); os.close(fd)
    try:
        upload.save(tmp); check=sqlite3.connect(tmp)
        integrity=check.execute('PRAGMA integrity_check').fetchone()[0]
        tables={x[0] for x in check.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        check.close()
        if integrity!='ok' or not {'patients','appointments','health_records'}.issubset(tables):return jsonify(error='The selected file is not a valid Suraksha Health Care SQLite backup'),400
        current=os.path.join(base,'patientcare.db'); backup=os.path.join(base,'patientcare_before_restore_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.db')
        if os.path.exists(current):shutil.copy2(current,backup)
        os.replace(tmp,current)
        # Run schema migrations and seed only missing reference/demo accounts after restore.
        init_db()
        audit('Restored database backup','database',details='Validated SQLite backup restored; prior database saved locally')
        return jsonify(message='Database restored and schema migrations applied. Restart Suraksha Health Care if any page still shows stale data.',previous_backup=os.path.basename(backup))
    except Exception as exc:return jsonify(error='Restore failed: '+str(exc)),500
    finally:
        if os.path.exists(tmp):os.remove(tmp)

@app.post('/api/admin/import-demo-patients')
@roles('Administrator')
def import_demo_patients():
    # Repeat-safe import: deterministic synthetic emails mark demo rows; no existing data is deleted.
    first=['Aarav','Aanya','Vivaan','Diya','Advik','Anaya','Ishaan','Meera','Kabir','Saanvi','Arjun','Ira','Reyansh','Kiara','Rohan','Tara','Dev','Nisha','Kunal','Mira']
    last=['Sharma','Rao','Patel','Nair','Reddy','Kumar','Mehta','Iyer','Joshi','Kulkarni','Singh','Das','Shetty','Verma','Menon','Gupta','Bose','Pillai','Naidu','Shah']
    genders=['Female','Male','Non-binary','Prefer not to say']; blood=['A+','A-','B+','B-','AB+','AB-','O+','O-']
    db=get_db(); before=db.execute("SELECT COUNT(*) c FROM patients WHERE email LIKE 'demo.patient.%@caresphere.invalid'").fetchone()['c']; rows=[]
    for i in range(1,1001):
        email=f'demo.patient.{i:04d}@caresphere.invalid'
        if db.execute('SELECT 1 FROM patients WHERE email=?',(email,)).fetchone():continue
        rows.append((f'{first[(i*7)%len(first)]} {last[(i*11)%len(last)]}',18+(i*13)%73,genders[i%len(genders)],f'900{i%10}{i:06d}',email,'',blood[i%len(blood)],'None recorded',f'900{i%10}{(i+1):06d}'))
    db.executemany('INSERT INTO patients(name,age,gender,phone,email,address,blood_group,allergies,emergency_contact) VALUES(?,?,?,?,?,?,?,?,?)',rows); db.commit(); total=db.execute("SELECT COUNT(*) c FROM patients WHERE email LIKE 'demo.patient.%@caresphere.invalid'").fetchone()['c']; db.close(); audit('Imported synthetic demo patients','patient',details=f'Added {len(rows)}; total demo records {total}')
    return jsonify(message=f'Added {len(rows)} synthetic patients. Existing records were preserved.',added=len(rows),total_demo_patients=total)

@app.get('/api/followups')
@roles('Administrator','Doctor')
def followups():
    db=get_db(); rows=db.execute("SELECT a.id,a.patient_id,p.name patient_name,p.phone,p.email,a.doctor,a.date,a.time,a.status,a.reason FROM appointments a LEFT JOIN patients p ON p.id=a.patient_id WHERE (a.status='Scheduled' AND date(a.date)>=date('now') AND date(a.date)<=date('now','+30 days')) OR (a.status IN ('No-show','Missed')) ORDER BY date(a.date),a.time").fetchall(); db.close(); return jsonify(rowdicts(rows))

@app.put('/api/patient-portal/profile')
@roles('Patient')
def patient_update_profile():
    pid=session.get('patient_id')
    if not pid:return jsonify(error='No patient profile is linked to this account'),404
    d=request.get_json() or {}; email=str(d.get('email','')).strip(); phone=str(d.get('phone','')).strip(); address=str(d.get('address','')).strip(); emergency=str(d.get('emergency_contact','')).strip()
    if len(email)>254 or len(phone)>40 or len(address)>500 or len(emergency)>40:return jsonify(error='One or more fields exceed the allowed length'),400
    if email and ('@' not in email or email.startswith('@') or email.endswith('@')):return jsonify(error='Enter a valid email address'),400
    db=get_db(); cur=db.execute('UPDATE patients SET email=?,phone=?,address=?,emergency_contact=? WHERE id=?',(email,phone,address,emergency,pid)); db.commit()
    db.execute('UPDATE app_users SET email=?,phone=? WHERE username=?',(email,phone,session['username']));db.commit();db.close()
    audit('Patient updated own contact details','patient',pid);return jsonify(message='Contact details updated')

@app.get('/api/admin/export/<dataset>')
@roles('Administrator')
def export_dataset(dataset):
    # Exports are administrator-only because they contain identifiable information.
    allowed={
      'patients':('SELECT id,name,age,gender,phone,email,address,blood_group,allergies,emergency_contact,created_at FROM patients ORDER BY id','patients.csv',['id','name','age','gender','phone','email','address','blood_group','allergies','emergency_contact','created_at']),
      'appointments':('SELECT a.id,p.name AS patient_name,a.doctor,a.date,a.time,a.status,a.reason FROM appointments a LEFT JOIN patients p ON p.id=a.patient_id ORDER BY a.date,a.time','appointments.csv',['id','patient_name','doctor','date','time','status','reason']),
      'health-records':('SELECT h.id,p.name AS patient_name,h.diagnosis,h.treatment,h.date,h.notes,h.temperature,h.heart_rate,h.systolic,h.diastolic,h.spo2,h.weight,h.respiratory_rate,h.blood_glucose FROM health_records h LEFT JOIN patients p ON p.id=h.patient_id ORDER BY h.date DESC','health_records.csv',['id','patient_name','diagnosis','treatment','date','notes','temperature','heart_rate','systolic','diastolic','spo2','weight','respiratory_rate','blood_glucose'])}
    if dataset not in allowed:return jsonify(error='Unknown export type'),404
    sql,filename,headers=allowed[dataset]; db=get_db(); rows=db.execute(sql).fetchall(); db.close(); out=io.StringIO(newline=''); writer=csv.writer(out); writer.writerow(headers)
    for row in rows:writer.writerow([row[k] for k in row.keys()])
    audit('Exported CSV','export',details=f'{dataset}; rows={len(rows)}')
    return send_file(io.BytesIO(('\ufeff'+out.getvalue()).encode('utf-8')),mimetype='text/csv; charset=utf-8',as_attachment=True,download_name=filename)

@app.get('/health')
@app.get('/api/health')
def health():return jsonify(status='ok',application='Suraksha Health Care',version='3.0')

if __name__=='__main__': app.run(host='127.0.0.1',port=int(os.getenv('PORT','5000')),debug=False)
