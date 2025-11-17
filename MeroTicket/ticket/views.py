# ticket/views.py
from django.shortcuts import render, redirect, get_object_or_404
from .models import TicketType, Ticket
from django.utils.crypto import get_random_string
import qrcode
from io import BytesIO
from django.core.files import File
from .models import Event, TicketType
from django.utils import timezone
from django.conf import settings
import uuid, os, json, requests, qr_code
from django.views.decorators.csrf import csrf_exempt
from io import BytesIO
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files import File
from reportlab.pdfgen import canvas






def home(request):
    events = Event.objects.all()
    return render(request, 'ticket/home.html', {'events': events})

def purchase_ticket(request, ticket_type_id):
    ticket_type = TicketType.objects.get(id=ticket_type_id)
    
    if ticket_type.sold >= ticket_type.limit:
        return render(request, 'ticket/sold_out.html', {'ticket_type': ticket_type})
    
    if request.method == 'POST':
        phone = request.POST.get('phone')
        # Payment success (simulate for now)
        ticket = Ticket.objects.create(
            ticket_type=ticket_type,
            purchaser_phone=phone,
            payment_status=True,
            status='Valid'
        )

        # Update sold count
        ticket_type.sold += 1
        ticket_type.save()

        # Generate QR
        qr_code_data = f"{ticket.id}-{get_random_string(10)}"
        qr_img = qrcode.make(qr_code_data)
        buffer = BytesIO()
        qr_img.save(buffer, 'PNG')
        ticket.qr_image.save(f'{ticket.id}.png', File(buffer))
        ticket.save()
        
        return redirect('ticket_success', ticket_id=ticket.id)
    
    return render(request, 'ticket/purchase.html', {'ticket_type': ticket_type})


def ticket_success(request, ticket_id):
    ticket = Ticket.objects.get(id=ticket_id)
    return render(request, 'ticket/success.html', {'ticket': ticket})

'''def buy_ticket(request, tickettype_id):
    ticket_type = get_object_or_404(TicketType, id=tickettype_id)

    # Check availability
    if ticket_type.limit <= 0:
        return render(request, 'ticket/sold_out.html', {'ticket_type': ticket_type})

    if request.method == 'POST':
        # STEP 1: Reduce ticket limit
        ticket_type.limit -= 1
        ticket_type.save()

        # STEP 2: Create ticket
        ticket = Ticket.objects.create(
            ticket_type=ticket_type,
            status='Pending',
            purchaser_phone=request.POST.get('phone', '')
        )

        # STEP 3: Generate QR code
        qr_img = qrcode.make(str(uuid.uuid4()))
        qr_io = BytesIO()
        qr_img.save(qr_io, 'PNG')
        ticket.qr_image.save(f"{ticket.id}.png", File(qr_io))
        ticket.save()

        # STEP 4: Return ticket ID for JS to use in redirect
        return JsonResponse({'ticket_id': ticket.id})

    return render(request, 'ticket/checkout.html', {
        'ticket_type': ticket_type,
    })'''

def buy_ticket(request, tickettype_id):
    ticket_type = get_object_or_404(TicketType, id=tickettype_id)

    return render(request, 'ticket/checkout.html', {
        'ticket_type': ticket_type,
        'KHALTI_PUBLIC_KEY': settings.KHALTI_PUBLIC_KEY,
    })

@csrf_exempt
def verify_payment(request):
    if request.method == "POST":
        data = json.loads(request.body)
        token = data.get("token")
        amount = data.get("amount")
        ticket_type_id = data.get("ticket_type_id")

        ticket_type = TicketType.objects.get(id=ticket_type_id)

        # Verify payment with Khalti
        headers = {"Authorization": f"Key {settings.KHALTI_SECRET_KEY}"}
        payload = {"token": token, "amount": amount}
        response = requests.post(settings.KHALTI_VERIFY_URL, payload, headers=headers)
        result = response.json()

        if result.get("idx"):
            # Payment successful
            # Reduce ticket limit
            ticket_type.limit -= 1
            ticket_type.save()

            # Create ticket
            ticket = Ticket.objects.create(
                ticket_type=ticket_type,
                status="Valid",
                purchaser_phone="",
            )

            # Generate QR
            qr_img = qrcode.make(str(uuid.uuid4()))
            qr_io = BytesIO()
            qr_img.save(qr_io, 'PNG')
            ticket.qr_image.save(f"{ticket.id}.png", File(qr_io))
            ticket.save()

            # Generate PDF receipt
            pdf_io = BytesIO()
            c = canvas.Canvas(pdf_io)
            c.drawString(100, 800, f"Ticket ID: {ticket.id}")
            c.drawString(100, 780, f"Event: {ticket_type.event.name}")
            c.drawString(100, 760, f"Ticket Type: {ticket_type.name}")
            c.drawImage(qr_io, 100, 600, width=150, height=150)
            c.save()
            pdf_io.seek(0)
            ticket.receipt_pdf.save(f"receipt_{ticket.id}.pdf", File(pdf_io))

            return JsonResponse({"success": True, "ticket_id": ticket.id})

    return JsonResponse({"success": False})