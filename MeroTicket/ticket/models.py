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

    purchaser_phone = models.CharField(max_length=20, blank=True)
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
