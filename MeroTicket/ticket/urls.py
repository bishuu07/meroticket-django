# ticket/urls.py
from django.urls import path
from . import views
from .views import  buy_ticket #verify_payment


urlpatterns = [
    path('', views.home, name='home'),
    #path('purchase/<int:ticket_type_id>/', views.purchase_ticket, name='purchase_ticket'),
    path("success/<uuid:ticket_id>/", views.ticket_success, name="ticket_success"),

    path('buy/<int:tickettype_id>/', buy_ticket, name='buy_ticket'),
    #path('verify-payment/', verify_payment, name='verify_payment'),
    path('initiate-khalti/', views.initiate_khalti, name='initiate_khalti'),
    path('khalti/callback/', views.khalti_callback, name='khalti_callback'),
    path('ticket/<uuid:ticket_id>/download/', views.download_ticket_pdf, name='download_ticket_pdf'),


]
