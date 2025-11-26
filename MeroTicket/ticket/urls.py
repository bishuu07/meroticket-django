# ticket/urls.py
from django.urls import path
from . import views
from .views import  buy_ticket #verify_payment
from django.contrib.auth import views as auth_views
from ticket import views as ticket_views



urlpatterns = [
    path('', views.home, name='home'),
    #path('purchase/<int:ticket_type_id>/', views.purchase_ticket, name='purchase_ticket'),
    path("success/<uuid:ticket_id>/", views.ticket_success, name="ticket_success"),

    path('buy/<int:tickettype_id>/', buy_ticket, name='buy_ticket'),
    #path('verify-payment/', verify_payment, name='verify_payment'),
    path('initiate-khalti/', views.initiate_khalti, name='initiate_khalti'),
    path('khalti/callback/', views.khalti_callback, name='khalti_callback'),
    path('ticket/<uuid:ticket_id>/download/', views.download_ticket_png, name='download_ticket_png'),
    #path('scan/', views.scanner_page, name='scanner_page'),
    path('api/verify-ticket/', views.verify_ticket, name='verify_ticket'),
    path("login/", auth_views.LoginView.as_view(template_name="auth/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="/"), name="logout"),
    path("dashboard/", ticket_views.user_dashboard, name="user_dashboard"),
   # path("scanner/", ticket_views.scanner_page, name="scanner"),
    path('scanner/', views.scanner_page, name='scanner_page'),





]
