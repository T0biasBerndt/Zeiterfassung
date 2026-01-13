from django.shortcuts import render, redirect
from django.urls import reverse
from django.core import signing
from django.core.signing import BadSignature, SignatureExpired
from django.http import HttpResponseForbidden, HttpResponse, HttpResponseBadRequest  # HTTP-Antwort für unautorisierte Zugriffe
from .forms import RegisterForm, LoginForm, WorkReportForm
from . import storage
import io
import csv
import json
import xml.etree.ElementTree as ET

# cookie settings
_COOKIE_NAME = 'acct_user'  # Name des Cookies, das den angemeldeten Nutzer speichert
_COOKIE_SALT = 'accounts-salt'  # Salt für das Signieren des Cookie-Inhalts
_COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # Lebensdauer des Cookies in Sekunden (eine Woche)

def _read_user_from_cookie(request):
    cookie = request.COOKIES.get(_COOKIE_NAME)
    if not cookie:
        return None
    try:
        # signiertes Token entschlüsseln/prüfen; max_age schützt gegen veraltete Cookies
        data = signing.loads(cookie, salt=_COOKIE_SALT, max_age=_COOKIE_MAX_AGE)
        # data expected to be dict with username and email
        if isinstance(data, dict) and 'username' in data:
            return data
    except (BadSignature, SignatureExpired):
        pass  # bei ungültiger Signatur oder abgelaufenem Token -> anonym
    return None

def _set_user_cookie(response, userdict):
    # signiert userdict und setzt ein HttpOnly-Cookie (keine JS-Zugriffe)
    token = signing.dumps(userdict, salt=_COOKIE_SALT)
    response.set_cookie(_COOKIE_NAME, token, httponly=True, samesite='Lax', max_age=_COOKIE_MAX_AGE)

def _clear_user_cookie(response):
    # löscht das Cookie (Abmelden)
    response.delete_cookie(_COOKIE_NAME)

def home(request):
    # liest den angemeldeten User aus dem Cookie und übergibt ihn an das Template
    user = _read_user_from_cookie(request)
    # bereite das leere Formular und die Reports des Benutzers vor
    report_form = WorkReportForm()  # leeres Formular zum Erstellen eines Berichts
    user_reports = []
    report_summary = None  # neu: Zusammenfassung initialisieren
    if user:
        user_reports = storage.get_reports_for_user(user.get('username'))  # lade Reports für aktuellen Nutzer
        # neu: berechne Summary (total + pro Modul) und gib sie ans Template weiter
        report_summary = storage.summarize_reports(user.get('username'))
    return render(request, 'accounts/home.html', {'user': user, 'report_form': report_form, 'reports': user_reports, 'report_summary': report_summary})

def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username'].strip()
            email = form.cleaned_data['email'].strip().lower()
            password = form.cleaned_data['password']

            # Standardrolle beim Anlegen ist 'user', upgrade_requested standardmäßig False
            ok, err = storage.add_user({'username': username, 'email': email, 'password': password, 'role': 'user', 'upgrade_requested': False})
            if not ok:
                if 'username' in err:
                    form.add_error('username', 'Username already exists')
                elif 'email' in err:
                    form.add_error('email', 'Email already registered')
                else:
                    form.add_error(None, err)
            else:
                # bei erfolgreicher Registrierung: redirect + setze signiertes Cookie mit Nutzerinfo (inkl. role und upgrade flag)
                resp = redirect(reverse('accounts:home'))
                _set_user_cookie(resp, {'username': username, 'email': email, 'role': 'user', 'upgrade_requested': False})
                return resp
    else:
        form = RegisterForm()
    # ensure templates can show current user in the top-right -> provide 'user' from cookie
    current_user = _read_user_from_cookie(request)  # liest signiertes Cookie falls vorhanden
    return render(request, 'accounts/register.html', {'form': form, 'user': current_user})  # user in context

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username'].strip()
            password = form.cleaned_data['password']
            user = storage.authenticate(username, password)
            if user:
                # bei erfolgreicher Authentifizierung: Cookie setzen und weiterleiten
                resp = redirect(reverse('accounts:home'))
                # user enthält jetzt auch 'role' und 'upgrade_requested' -> wir setzen diese in das Cookie
                _set_user_cookie(resp, {'username': user['username'], 'email': user.get('email'), 'role': user.get('role', 'user'), 'upgrade_requested': user.get('upgrade_requested', False)})
                return resp
            form.add_error(None, 'Invalid credentials')
    else:
        form = LoginForm()
    # provide 'user' so base.html can render the top-right link/status consistently
    current_user = _read_user_from_cookie(request)  # liest signiertes Cookie falls vorhanden
    return render(request, 'accounts/login.html', {'form': form, 'user': current_user})  # user in context

def logout_view(request):
    # Cookie löschen und zur Startseite weiterleiten
    resp = redirect(reverse('accounts:home'))
    _clear_user_cookie(resp)
    return resp

# new: profile view showing current user's details; anonymous users -> redirect to login
def profile(request):
    current_user = _read_user_from_cookie(request)  # lese current user aus Cookie
    if not current_user:
        return redirect(reverse('accounts:login'))  # nicht eingeloggt -> zur Login-Seite

    # prepare context always including the current user
    context = {'user': current_user}

    # wenn der eingeloggte Nutzer die Rolle 'admin' hat, lade alle User aus der JSON-Datei
    if current_user.get('role') == 'admin':
        users = storage.load_users()  # lade vollständige User-Liste aus accounts.json
        context['users'] = users  # füge die Liste zum Template-Kontext hinzu (nur für Admins sichtbar)
        # neu: erzeuge eine Liste mit den Nutzern, die ein Upgrade angefragt haben
        pending = [u for u in users if u.get('upgrade_requested')]  # list comprehension filtert Anfragen
        context['pending'] = pending  # füge pending-Requests zum Kontext hinzu

    # render profile template mit user (und ggf. users, pending)
    return render(request, 'accounts/user.html', context)

# new: POST-endpoint, nur Admins dürfen Rollen anderer Nutzer ändern
def change_role(request):
    # lese aktuell angemeldeten Nutzer aus Cookie
    current_user = _read_user_from_cookie(request)
    # prüfe Admin-Rechte; wenn nicht admin -> 403 Forbidden
    if not current_user or current_user.get('role') != 'admin':
        return HttpResponseForbidden("Forbidden")  # neu: verweigere Zugriff für Nicht-Admins

    if request.method != 'POST':
        return redirect(reverse('accounts:profile'))  # nur POST erlaubt, sonst zurück

    # lese POST-Parameter username und role
    username = request.POST.get('username')
    new_role = request.POST.get('role')

    # Aktualisiere Rolle in der JSON-Datei (keine weitere Validierung)
    if username and new_role:
        storage.update_user_role(username, new_role)  # neu: schreibt die neue Rolle in accounts.json

    # zurück zur Profil-/Admin-Seite
    return redirect(reverse('accounts:profile'))

# new: POST endpoint für Upgrade-Anfragen (nur angemeldete nicht-admins)
def request_upgrade(request):
    current_user = _read_user_from_cookie(request)  # lese aktuellen Nutzer aus Cookie
    if not current_user:
        return redirect(reverse('accounts:login'))  # nicht eingeloggt -> login

    # Admins sollten nicht upgraden
    if current_user.get('role') == 'admin':
        return redirect(reverse('accounts:profile'))

    if request.method != 'POST':
        return redirect(reverse('accounts:profile'))

    username = current_user.get('username')
    if username and not current_user.get('upgrade_requested'):
        # storage.request_upgrade returns True/False (kein target mehr)
        changed = storage.request_upgrade(username)
        if changed:
            # aktualisiere Cookie mit neuem Flag (kein upgrade_target)
            updated_user = {
                'username': current_user.get('username'),
                'email': current_user.get('email'),
                'role': current_user.get('role', 'user'),
                'upgrade_requested': True,
            }
            resp = redirect(reverse('accounts:profile'))
            _set_user_cookie(resp, updated_user)
            return resp

    return redirect(reverse('accounts:profile'))

# Admin akzeptiert eine Upgrade-Anfrage (POST)
def accept_upgrade(request):
    current_user = _read_user_from_cookie(request)
    if not current_user or current_user.get('role') != 'admin':
        return HttpResponseForbidden("Forbidden")
    if request.method != 'POST':
        return redirect(reverse('accounts:profile'))
    username = request.POST.get('username')
    if username:
        storage.accept_upgrade(username)  # setzt role auf upgrade_target und löscht Flags
    return redirect(reverse('accounts:profile'))

# new: Admin lehnt eine Upgrade-Anfrage ab (POST)
def deny_upgrade(request):
    current_user = _read_user_from_cookie(request)
    if not current_user or current_user.get('role') != 'admin':
        return HttpResponseForbidden("Forbidden")
    if request.method != 'POST':
        return redirect(reverse('accounts:profile'))
    username = request.POST.get('username')
    if username:
        storage.deny_upgrade(username)  # löscht upgrade_requested und upgrade_target
    return redirect(reverse('accounts:profile'))

# neu: POST-Endpoint zum Anlegen eines Arbeitsberichts
def create_report(request):
    if request.method != 'POST':
        return redirect(reverse('accounts:home'))
    current_user = _read_user_from_cookie(request)
    if not current_user:
        return redirect(reverse('accounts:login'))  # nur angemeldete Nutzer dürfen Berichte anlegen
    form = WorkReportForm(request.POST)
    if form.is_valid():
        minutes = form.cleaned_data['minutes']
        date = form.cleaned_data['date']  # DateField -> date object, str() ok
        module = form.cleaned_data['module']
        content = form.cleaned_data['content']
        # speichere den Bericht in der JSON (owner = username)
        storage.add_report(current_user.get('username'), minutes, date, module, content)
    # egal ob Erfolg oder nicht, zurück zur Startseite
    return redirect(reverse('accounts:home'))

def _role_is_vip_or_admin(userdict):
    # helper: prüft ob Rolle 'vip' oder 'admin' ist
    if not userdict:
        return False
    return userdict.get('role') in ('vip', 'admin')

# new: export user's reports in json/csv/xml (GET param 'format')
def export_reports(request):
    current_user = _read_user_from_cookie(request)
    if not current_user or not _role_is_vip_or_admin(current_user):
        return HttpResponseForbidden("Forbidden")  # nur VIP/Admin erlaubt

    fmt = request.GET.get('format', 'json').lower()
    username = current_user.get('username')
    reports = storage.get_reports_for_user(username)

    if fmt == 'json':
        payload = json.dumps(reports, ensure_ascii=False, indent=2)
        resp = HttpResponse(payload, content_type='application/json; charset=utf-8')
        resp['Content-Disposition'] = f'attachment; filename="{username}_reports.json"'
        return resp

    if fmt == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        # header
        writer.writerow(['date', 'minutes', 'module', 'content'])
        for r in reports:
            writer.writerow([r.get('date', ''), r.get('minutes', 0), r.get('module', ''), r.get('content', '')])
        resp = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = f'attachment; filename="{username}_reports.csv"'
        return resp

    if fmt == 'xml':
        root = ET.Element('reports')
        for r in reports:
            item = ET.SubElement(root, 'report')
            ET.SubElement(item, 'date').text = str(r.get('date', ''))
            ET.SubElement(item, 'minutes').text = str(r.get('minutes', 0))
            ET.SubElement(item, 'module').text = r.get('module', '')
            ET.SubElement(item, 'content').text = r.get('content', '')
        xml_bytes = ET.tostring(root, encoding='utf-8', xml_declaration=True)
        resp = HttpResponse(xml_bytes, content_type='application/xml; charset=utf-8')
        resp['Content-Disposition'] = f'attachment; filename="{username}_reports.xml"'
        return resp

    return HttpResponseBadRequest("Unknown format")

# new: upload CSV to overwrite user's reports (only VIP/Admin)
def upload_reports(request):
    current_user = _read_user_from_cookie(request)
    if not current_user or not _role_is_vip_or_admin(current_user):
        return HttpResponseForbidden("Forbidden")

    if request.method != 'POST':
        return redirect(reverse('accounts:home'))

    uploaded = request.FILES.get('csv_file')
    if not uploaded:
        return HttpResponseBadRequest("No file uploaded")

    try:
        # read as text
        text = uploaded.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(text))
        new_reports = []
        for row in reader:
            # expect headers: date, minutes, module, content (case-insensitive)
            # use safe extraction
            date = row.get('date') or row.get('Date') or ''
            minutes = row.get('minutes') or row.get('Minutes') or '0'
            module = row.get('module') or row.get('Module') or ''
            content = row.get('content') or row.get('Content') or ''
            try:
                minutes_int = int(minutes)
            except Exception:
                minutes_int = 0
            new_reports.append({'date': str(date), 'minutes': minutes_int, 'module': module, 'content': content})
        # overwrite user's reports
        storage.overwrite_user_reports(current_user.get('username'), new_reports)
    except Exception as e:
        return HttpResponseBadRequest("Invalid CSV file")

    return redirect(reverse('accounts:home'))
