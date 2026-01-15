from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.home, name='home'),  # Startseite zeigt den Status / aktuellen Nutzer
    path('register/', views.register, name='register'),  # Registrierungsseite
    path('login/', views.login_view, name='login'),  # Login-Seite
    path('logout/', views.logout_view, name='logout'),  # Logout-Route löscht das Cookie
    path('user/', views.profile, name='profile'),  # Benutzerprofil-Seite, erreichbar unter /user/
    path('user/change-role/', views.change_role, name='change_role'),  # Admin-Endpoint zum Ändern von Rollen
    path('user/request-upgrade/', views.request_upgrade, name='request_upgrade'),  # Endpoint, wenn Nutzer Upgrade anfragt
    path('user/accept-upgrade/', views.accept_upgrade, name='accept_upgrade'),  # Admin akzeptiert Upgrade-Anfrage
    path('user/deny-upgrade/', views.deny_upgrade, name='deny_upgrade'),  # Admin lehnt Upgrade-Anfrage ab
    # Endpoint zum Erstellen von Arbeitsberichten
    path('reports/create/', views.create_report, name='create_report'),
    # delete report endpoint
    path('reports/delete/', views.delete_report , name='delete_report'),
    # export und upload (nur für VIP/Admin)
    path('reports/export/', views.export_reports, name='export_reports'),
    path('reports/upload/', views.upload_reports, name='upload_reports'),
]
