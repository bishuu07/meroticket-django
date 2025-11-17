# ticket/urls.py
from django.urls import path
from . import views
from .views import  buy_ticket, verify_payment


urlpatterns = [
    path('', views.home, name='home'),
    path('purchase/<int:ticket_type_id>/', views.purchase_ticket, name='purchase_ticket'),
    path('success/<int:ticket_id>/', views.ticket_success, name='ticket_success'),
    path('buy/<int:tickettype_id>/', buy_ticket, name='buy_ticket'),
     path('verify-payment/', verify_payment, name='verify_payment'),

]
