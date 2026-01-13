import json
import os
from django.conf import settings

# Pfad zur JSON-Datei im Projektverzeichnis (BASE_DIR/accounts.json)
_DATA_FILE = os.path.join(str(settings.BASE_DIR), 'accounts.json')

def _ensure_file():
    # sorgt dafür, dass die Datei existiert; falls nicht, erstelle sie und schreibe ein leeres Array
    dirpath = os.path.dirname(_DATA_FILE) or '.'
    os.makedirs(dirpath, exist_ok=True)  # erstelle Verzeichnis falls nötig
    if not os.path.exists(_DATA_FILE):
        with open(_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)  # lege leere Liste als JSON an

def load_users():
    # liest die gesamte Liste von Usern aus der JSON-Datei zurück
    _ensure_file()  # stelle sicher, dass Datei existiert
    try:
        with open(_DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)  # lade JSON-Inhalt
            return data if isinstance(data, list) else []  # falls Datei kaputt -> leere Liste
    except Exception:
        return []  # bei Fehlern einfach leere Liste zurückgeben

def save_users(users):
    # schreibt die komplette User-Liste in die JSON-Datei (einfach, ohne atomare Operationen)
    with open(_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)  # überschreibe Datei

def add_user(userobj):
    """
    Fügt das gegebene userobj ans Ende der Liste an.
    Keine Duplikatprüfung, kein Hashing — minimal und unsicher.
    """
    users = load_users()  # lade aktuelle Liste
    # speichere username, email, password, role und upgrade_requested (kein upgrade_target)
    users.append({
        'username': userobj.get('username'),
        'email': userobj.get('email'),
        'password': userobj.get('password'),
        'role': userobj.get('role', 'user'),  # Rolle, default 'user'
        'upgrade_requested': userobj.get('upgrade_requested', False),  # Anfrage-Flag
        # upgrade_target entfernt
    })
    save_users(users)
    return True, None  # Erfolg

def find_user(username):
    # suche ersten User mit gegebenem Benutzernamen (oder None)
    users = load_users()
    for u in users:
        if u.get('username') == username:
            return u
    return None

def authenticate(username, password):
    # sehr einfache Authentifizierung: vergleiche Klartext-Passwort
    user = find_user(username)
    if not user:
        return None
    if user.get('password') == password:
        # gib ein kleines Objekt zurück (inkl. role und upgrade_requested), kein upgrade_target
        return {
            'username': user.get('username'),
            'email': user.get('email'),
            'role': user.get('role', 'user'),
            'upgrade_requested': user.get('upgrade_requested', False),
        }
    return None

# neu: Funktion, die die Rolle eines Nutzers in der JSON-Datei ändert
def update_user_role(username, new_role):
    # lade alle Nutzer (liest accounts.json)
    users = load_users()
    changed = False  # Flag, ob wir eine Änderung vorgenommen haben
    for u in users:
        if u.get('username') == username:
            u['role'] = new_role  # setze das role-Feld auf den neuen Wert
            changed = True
            break
    if changed:
        save_users(users)  # speichere die aktualisierte Liste zurück in die Datei
        return True  # Änderung erfolgreich
    return False  # Benutzer nicht gefunden -> keine Änderung

# neu: Funktion, die die Upgrade-Anfrage eines Nutzers in der JSON-Datei setzt
def request_upgrade(username):
    """
    Markiert eine Upgrade-Anfrage:
    - setzt nur upgrade_requested = True
    - kein upgrade_target wird gespeichert
    Gibt True zurück bei erfolgreicher Markierung, sonst False.
    """
    users = load_users()
    changed = False
    for u in users:
        if u.get('username') == username:
            role = u.get('role', 'user')
            # Admins dürfen keine Anfrage stellen
            if role == 'admin':
                return False
            # falls bereits angefragt, nichts tun
            if u.get('upgrade_requested'):
                return False
            u['upgrade_requested'] = True  # nur Flag setzen
            changed = True
            break
    if changed:
        save_users(users)
        return True
    return False

def accept_upgrade(username):
    """
    Admin akzeptiert Anfrage: berechne Ziel anhand aktueller Rolle:
      user -> vip, vip -> admin, sonst keine Änderung.
    Setze role auf Ziel und lösche upgrade_requested.
    """
    users = load_users()
    changed = False
    for u in users:
        if u.get('username') == username:
            current = u.get('role', 'user')
            if current == 'user':
                new_role = 'vip'
            elif current == 'vip':
                new_role = 'admin'
            else:
                # falls already admin oder unbekannt, nichts tun
                return False
            u['role'] = new_role  # setze neue Rolle
            u['upgrade_requested'] = False  # clear request flag
            changed = True
            break
    if changed:
        save_users(users)
        return True
    return False

def deny_upgrade(username):
    """
    Admin lehnt ab: setze upgrade_requested False.
    """
    users = load_users()
    changed = False
    for u in users:
        if u.get('username') == username:
            if u.get('upgrade_requested'):
                u['upgrade_requested'] = False
                changed = True
            break
    if changed:
        save_users(users)
        return True
    return False

"""
/////////////////work_reports.json/////////////////
"""

# Pfad zur JSON-Datei für Arbeitsberichte im Projektverzeichnis
_REPORTS_FILE = os.path.join(str(settings.BASE_DIR), 'work_reports.json')  # speichert alle Arbeitsberichte

def _ensure_reports_file():
    # sorgt dafür, dass die Datei für Reports existiert
    dirpath = os.path.dirname(_REPORTS_FILE) or '.'
    os.makedirs(dirpath, exist_ok=True)  # erstelle Verzeichnis falls nötig
    if not os.path.exists(_REPORTS_FILE):
        with open(_REPORTS_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)  # lege leere Liste als JSON an

def load_reports():
    # liest alle Arbeitsberichte aus work_reports.json
    _ensure_reports_file()  # stelle sicher, dass Datei existiert
    try:
        with open(_REPORTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)  # lade JSON-Inhalt
            return data if isinstance(data, list) else []  # falls Datei kaputt -> leere Liste
    except Exception:
        return []  # bei Fehlern einfach leere Liste zurückgeben

def save_reports(reports):
    # schreibt die komplette Reports-Liste in die JSON-Datei (einfach, ohne atomare Operationen)
    with open(_REPORTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(reports, f, ensure_ascii=False, indent=2)  # überschreibe Datei

def add_report(username, minutes, date_str, module, content):
    """
    Fügt einen Bericht hinzu:
    - username: der Eigentümer des Berichts
    - minutes: ganzzahlige Anzahl Minuten
    - date_str: Datum als String (z.B. '2026-01-10')
    - module: Modulbezeichnung
    - content: kurzer Berichtstext
    """
    reports = load_reports()  # lade aktuelle Liste
    # einfaches Report-Objekt, keine Validierung (wie gewünscht minimal)
    report = {
        'username': username,       # Besitzer des Berichts
        'minutes': int(minutes),    # gearbeitete Minuten
        'date': str(date_str),      # Datum als String
        'module': module,           # Modul-Name
        'content': content,         # Berichtstext
    }
    reports.append(report)         # füge Bericht ans Ende der Liste an
    save_reports(reports)          # speichere aktualisierte Liste
    return True

def get_reports_for_user(username):
    # gibt alle Reports zurück, die zum gegebenen username gehören
    reports = load_reports()
    return [r for r in reports if r.get('username') == username]

# neu: Fasse Berichte pro Modul zusammen und berechne Prozentsatz der Gesamtzeit
def summarize_reports(username):
    """
    Liefert eine Zusammenfassung der Arbeitszeit des Benutzers:
    {
      'total_minutes': <int>,
      'by_module': [
         {'module': 'ModulA', 'minutes': 120, 'percent': 40.0},
         ...
      ]
    }
    """
    reports = get_reports_for_user(username)  # lade alle Reports des Nutzers
    totals = {}  # sammle Minuten pro Modul
    for r in reports:
        mod = (r.get('module') or 'unknown')  # Modul-Name, fallback 'unknown'
        try:
            mins = int(r.get('minutes', 0))  # Minuten als int
        except Exception:
            mins = 0
        totals[mod] = totals.get(mod, 0) + mins  # aufsummieren

    total_all = sum(totals.values())  # gesamte Minuten aller Module

    # Baue die Liste mit Prozentangaben
    by_module = []
    for mod, mins in totals.items():
        percent = (mins / total_all * 100) if total_all else 0  # Prozentanteil berechnen
        by_module.append({
            'module': mod,
            'minutes': mins,
            'percent': round(percent, 2),  # auf 2 Nachkommastellen runden
        })

    # sortiere absteigend nach Minuten
    by_module.sort(key=lambda x: x['minutes'], reverse=True)

    return {
        'total_minutes': total_all,
        'by_module': by_module,
    }

def overwrite_user_reports(username, new_reports):
    """
    Ersetzt alle Reports des gegebenen username mit new_reports.
    new_reports: Liste von dicts mit keys: minutes, date, module, content (username wird gesetzt).
    """
    reports = load_reports()  # lade alle existierenden Reports
    # entferne vorhandene Reports des Users
    reports = [r for r in reports if r.get('username') != username]
    # stelle sicher, dass jedes neue Report-Objekt den username enthält
    for r in new_reports:
        r['username'] = username
        # minimal: stelle sicher, dass minutes ganzzahlig ist
        try:
            r['minutes'] = int(r.get('minutes', 0))
        except Exception:
            r['minutes'] = 0
        r['date'] = str(r.get('date', ''))
        r['module'] = r.get('module', '')
        r['content'] = r.get('content', '')
        reports.append(r)
    save_reports(reports)  # speichere die kombinierte Liste zurück
    return True
