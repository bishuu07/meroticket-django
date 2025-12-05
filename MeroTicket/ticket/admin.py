from django.contrib import admin
from .models import TicketType, Ticket, ScanLog, Event
from django.utils.html import format_html


from django.contrib import admin
from django.db.models import Sum, Count
from .models import ScanLog, Ticket, TicketType, Event, Advertisement, SiteSettings

# -------------------------------
# ScanLog Admin (detailed view)
# -------------------------------
@admin.register(ScanLog)
class ScanLogAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'staff', 'scanned_at', 'result')
    list_filter = ('result', 'scanned_at')
    search_fields = ('ticket__id', 'staff__username')
    ordering = ('-scanned_at',)

# -------------------------------
# Staff-wise Scan Stats Admin
# -------------------------------
# -------------------------------
# Staff-wise Scan Stats Admin
# -------------------------------
class StaffScanStatsAdmin(admin.ModelAdmin):
    list_display = ('username', 'tickets_scanned', 'total_revenue')
    search_fields = ('username',)

    # Show username instead of 'staff'
    def username(self, obj):
        return obj.username
    username.short_description = 'Staff'

    # Aggregate total tickets scanned
    def tickets_scanned(self, obj):
        return ScanLog.objects.filter(staff=obj).count()
    tickets_scanned.short_description = 'Tickets Scanned'

    # Aggregate total revenue for tickets scanned
    def total_revenue(self, obj):
        total = ScanLog.objects.filter(staff=obj).aggregate(
            total=Sum('ticket__ticket_type__price')
        )['total'] or 0
        return f"Rs. {total}"
    total_revenue.short_description = 'Total Revenue'

# Proxy model for staff stats
from django.contrib.auth.models import User

class StaffUser(User):
    class Meta:
        proxy = True
        verbose_name = 'Staff User Stats'
        verbose_name_plural = 'Staff User Stats'

admin.site.register(StaffUser, StaffScanStatsAdmin)


# -------------------------------
# TicketType, Ticket, Event, Advertisement, SiteSettings Admin
# -------------------------------

@admin.register(TicketType)
class TicketTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'valid_from', 'valid_until', 'active')
    list_filter = ('active',)
    search_fields = ('name',)
    ordering = ('-valid_from',)

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        'id_short', 'ticket_type', 'purchaser_phone',
        'payment_status_display', 'status', 'used_by', 'used_time', 'created_at', 'qr_preview'
    )
    list_filter = ('status', 'payment_status', 'ticket_type')
    search_fields = ('id', 'purchaser_phone', 'khalti_ref')
    readonly_fields = ('id', 'qr_image', 'receipt_pdf', 'created_at')
    ordering = ('-created_at',)

    def id_short(self, obj):
        return str(obj.id)[:8]
    id_short.short_description = 'Ticket ID'

    def payment_status_display(self, obj):
        return 'Paid' if obj.payment_status == 'PAID' else 'Unpaid'
    payment_status_display.short_description = 'Payment'

    def qr_preview(self, obj):
        if obj.qr_image:
            return format_html('<img src="{}" style="width:80px;height:80px;" />', obj.qr_image.url)
        return '-'
    qr_preview.short_description = 'QR Code'

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['name', 'date', 'active', 'location']
    fields = ['name', 'image', 'description', 'active', 'location', 'date']

@admin.register(Advertisement)
class AdvertisementAdmin(admin.ModelAdmin):
    list_display = ('id', 'text', 'active', 'image_preview')
    list_editable = ('active',)
    list_filter = ('active',)
    search_fields = ('text',)
    readonly_fields = ('image_preview',)

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:80px; border-radius:6px;" />', obj.image.url)
        return "-"
    image_preview.short_description = 'Image Preview'

admin.site.register(SiteSettings)












