from django import forms

class RegisterForm(forms.Form):
    username = forms.CharField(max_length=150)  # Feld für Benutzernamen
    email = forms.EmailField()  # Feld für E-Mail
    password = forms.CharField(widget=forms.PasswordInput)  # Passwort-Eingabe (versteckt)
    password2 = forms.CharField(widget=forms.PasswordInput, label='Confirm password')  # Bestätigungspasswort

    def clean(self):
        # überprüft, ob Passwort und Bestätigung übereinstimmen
        cleaned = super().clean()
        if cleaned.get('password') != cleaned.get('password2'):
            raise forms.ValidationError("Passwords do not match")
        return cleaned

class LoginForm(forms.Form):
    username = forms.CharField()  # Login-Benutzername
    password = forms.CharField(widget=forms.PasswordInput)  # Login-Passwort

class WorkReportForm(forms.Form):
    minutes = forms.IntegerField(min_value=0, label='Minutes worked')  # Anzahl der Minuten, >=0
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label='Date')  # Datumsauswahl
    module = forms.CharField(max_length=200, label='Module')  # Modulbezeichnung
    content = forms.CharField(widget=forms.Textarea(attrs={'rows':3}), label='Short report')  # kurzer Bericht
