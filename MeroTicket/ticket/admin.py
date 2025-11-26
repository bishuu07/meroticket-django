from django.contrib import admin
from .models import TicketType, Ticket, ScanLog, Event
from django.utils.html import format_html


# -------------------------------
# TicketType Admin
# -------------------------------
@admin.register(TicketType)
class TicketTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'valid_from', 'valid_until', 'active')
    list_filter = ('active',)
    search_fields = ('name',)
    ordering = ('-valid_from',)


# -------------------------------
# Ticket Admin
# -------------------------------
@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        'id_short',
        'ticket_type',
        'purchaser_phone',
        'payment_status_display',
        'status',
        'used_by',
        'used_time',
        'created_at',
        'qr_preview'
    )
    list_filter = ('status', 'payment_status', 'ticket_type')
    search_fields = ('id', 'purchaser_phone', 'khalti_ref')
    readonly_fields = ('id', 'qr_image', 'receipt_pdf', 'created_at')

    ordering = ('-created_at',)

    # -------------------------------
    # Custom methods for admin display
    # -------------------------------
    def id_short(self, obj):
        return str(obj.id)[:8]  # show first 8 chars
    id_short.short_description = 'Ticket ID'

    def payment_status_display(self, obj):
        return 'Paid' if obj.payment_status else 'Unpaid'
    payment_status_display.short_description = 'Payment'

    def qr_preview(self, obj):
        if obj.qr_image:
            return format_html('<img src="{}" style="width:80px;height:80px;" />', obj.qr_image.url)
        return '-'
    qr_preview.short_description = 'QR Code'


# -------------------------------
# ScanLog Admin
# -------------------------------
@admin.register(ScanLog)
class ScanLogAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'staff', 'scanned_at', 'result')
    list_filter = ('result', 'scanned_at')
    search_fields = ('ticket__id', 'staff__username')
    ordering = ('-scanned_at',)


class TicketTypeInline(admin.TabularInline):
    model = TicketType
    extra = 1

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['name', 'date', 'active']
    fields = ['name', 'image', 'logo', 'description', 'active', 'date']
    inlines = [TicketTypeInline]

'''@admin.register(ScanLog)
class ScanLogAdmin(admin.ModelAdmin):
    list_display = ("ticket", "staff", "scanned_at", "result")
    search_fields = ("ticket__id", "staff__username", "result")'''