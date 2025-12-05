import uuid
import secrets
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Event(models.Model):
    name = models.CharField(max_length=200)
    image = models.ImageField(upload_to='event_images/')
    description = models.TextField(blank=True, null=True)
    active = models.BooleanField(default=True)  # Show on frontend or not
    date = models.DateTimeField()
    location = models.CharField(max_length=255, blank=True, null=True)
    

    
    def __str__(self):
        return self.name


class TicketType(models.Model):
    name = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='ticket_types')
    limit = models.PositiveIntegerField(default=1000)  # maximum tickets
    sold = models.PositiveIntegerField(default=0)  # auto-increment when tickets are purchased
    active = models.BooleanField(default=True)  # Show on frontend or not
    
    # Validity window
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()

    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Ticket(models.Model):
    STATUS_CHOICES = [
        ("VALID", "Valid"),
        ("USED", "Used"),
        ("CANCELLED", "Cancelled"),
    ]

    PAYMENT_CHOICES = [
        ("PENDING", "Pending"),
        ("PAID", "Paid"),
        ("FAILED", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_type = models.ForeignKey(TicketType, on_delete=models.CASCADE)
    #serial_number = models.PositiveIntegerField(null=True, blank=True, editable=False)
    purchaser_phone = models.CharField(max_length=20, blank=True)
    purchaser_name = models.CharField(max_length=200, null=True, blank=True)

    purchase_time = models.DateTimeField(auto_now_add=True)

    payment_status = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default="PENDING")
    khalti_ref = models.CharField(max_length=200, blank=True)

    # Extremely secure unique token for scanning
    qr_token = models.CharField(max_length=64, unique=True, editable=False)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="VALID")
    used_time = models.DateTimeField(null=True, blank=True)
    used_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)


    qr_image = models.ImageField(upload_to="qr_codes/", blank=True)
    receipt_pdf = models.FileField(upload_to="receipts/", blank=True)

    def save(self, *args, **kwargs):
        # Generate secure token only once
        if not self.qr_token:
            self.qr_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ticket_type.name} - {self.id}"




class ScanLog(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    staff = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    scanned_at = models.DateTimeField(auto_now_add=True)
    result = models.CharField(max_length=30)

    def __str__(self):
        return f"{self.ticket.id} scanned by {self.staff}"
    
class StaffScanLog(models.Model):
    staff = models.ForeignKey(
        'auth.User', 
        on_delete=models.CASCADE, 
        limit_choices_to={'is_staff': True}
    )
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    ticket_type = models.ForeignKey(TicketType, on_delete=models.CASCADE)
    scanned_at = models.DateTimeField(auto_now_add=True)
    result = models.CharField(max_length=30)  # e.g., VALID, USED, INVALID
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Ticket price at scan

    def __str__(self):
        return f"{self.staff.username} scanned {self.ticket.qr_token}"

    class Meta:
        ordering = ['-scanned_at']

    

class PaymentOrder(models.Model):
    purchase_order_id = models.CharField(max_length=50, unique=True)
    ticket_type = models.ForeignKey(TicketType, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)   # ← ADDED
    phone = models.CharField(max_length=20)
    raw_response = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    quantity = models.PositiveIntegerField(default=1)   # ← NEW



class FonepayQRRequest(models.Model):
    """
    Stores dynamic QR requests to FonePay so we can map PRN -> PaymentOrder -> Ticket creation.
    """
    prn = models.CharField(max_length=50, unique=True)
    payment_order = models.ForeignKey("PaymentOrder", on_delete=models.CASCADE, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    remarks1 = models.CharField(max_length=160, blank=True)
    remarks2 = models.CharField(max_length=50, blank=True)
    raw_response = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"FonepayPRN {self.prn} - {self.amount}"






class SiteSettings(models.Model):
    
    phone_number = models.CharField(max_length=50, blank=True, null=True)
    phone_number2 = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    class Meta:
        verbose_name = "Site Setting"
        verbose_name_plural = "Site Settings"

    def __str__(self):
        return "Website Settings"
    

class Advertisement(models.Model):
    image = models.ImageField(upload_to="ads/", blank=True, null=True)
    text = models.CharField(max_length=255, blank=True, null=True)
    active = models.BooleanField(default=True)
    video = models.FileField(upload_to='ads/videos/', null=True, blank=True)

from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum, Count, F
from django.utils import timezone
from .models import Ticket, TicketType


