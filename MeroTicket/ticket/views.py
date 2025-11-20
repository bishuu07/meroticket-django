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
import uuid, os, json, requests, qr_code, logging
from django.views.decorators.csrf import csrf_exempt
from io import BytesIO
from django.http import HttpResponse, JsonResponse,  HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.core.files import File
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from django.urls import reverse
from reportlab.lib.pagesizes import letter









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

# ---------------------------------------------------------
# 1) Show checkout page (no ticket created yet)
# ---------------------------------------------------------
'''def buy_ticket(request, tickettype_id):
    ticket_type = get_object_or_404(TicketType, id=tickettype_id)

    # Render checkout page that collects (optional) phone and initiates payment
    return render(request, 'ticket/checkout.html', {
        'ticket_type': ticket_type,
        'KHALTI_PUBLIC_KEY': settings.KHALTI_PUBLIC_KEY,
    })


# ---------------------------------------------------------
# 2) Initiate Khalti payment (server-side call to Khalti /initiate/)
#    Client posts JSON: { ticket_type_id: <id>, phone: "<phone>" }
#    Server returns Khalti response with payment_url (pidx)
# ---------------------------------------------------------
@csrf_exempt
def initiate_khalti(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        payload = json.loads(request.body)
        ticket_type_id = payload.get("ticket_type_id")
        phone = payload.get("phone", "")
        ticket_type = TicketType.objects.get(id=ticket_type_id)
    except Exception as e:
        return JsonResponse({"error": "Invalid payload or ticket type"}, status=400)

    # build unique purchase_order_id
    purchase_order_id = f"ORDER-{uuid.uuid4().hex[:12]}"

    # return_url must be absolute — use the callback route
    return_url = request.build_absolute_uri(reverse('khalti_callback'))

    initiate_payload = {
        "return_url": return_url,
        "website_url": settings.KHALTI_INITIATE_URL.split('/epayment')[0].replace('https://', 'https://'),  # not strictly necessary
        "amount": int(ticket_type.price * 100),  # paisa
        "purchase_order_id": purchase_order_id,
        "purchase_order_name": f"{ticket_type.event.name} - {ticket_type.name}",
        "customer_info": {
            "phone": phone
        }
    }

    headers = {
        "Authorization": f"Key {settings.KHALTI_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    # call Khalti initiate endpoint
    try:
        resp = requests.post(settings.KHALTI_INITIATE_URL, json=initiate_payload, headers=headers, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        return JsonResponse({"error": "Failed to contact Khalti", "details": str(e)}, status=500)

    resp_json = resp.json()
    # Response normally contains: pidx, payment_url, expires_at, expires_in
    # Send it to the client so the client can redirect to payment_url
    return JsonResponse(resp_json)


# ---------------------------------------------------------
# 3) Khalti callback (return_url). Khalti will redirect the user here
#    with query params including pidx and status. We then call lookup to verify.
#    Example callback params: ?pidx=...&status=Completed&purchase_order_id=...
# ---------------------------------------------------------
def khalti_callback(request):
    pidx = request.GET.get("pidx")
    status = request.GET.get("status")
    purchase_order_id = request.GET.get("purchase_order_id")  # matches our purchase_order_id
    # optionals: txnId, tidx, amount, mobile, purchase_order_name, etc.

    if not pidx:
        return HttpResponseBadRequest("Missing pidx")

    # Do lookup/verify with Khalti using pidx
    headers = {
        "Authorization": f"Key {settings.KHALTI_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    lookup_payload = {"pidx": pidx}
    try:
        r = requests.post(settings.KHALTI_VERIFY_URL, json=lookup_payload, headers=headers, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        return HttpResponse("Error verifying payment with Khalti: " + str(e), status=500)

    lookup = r.json()
    # lookup sample: { "pidx": "...", "total_amount": 1000, "status": "Completed", "transaction_id": "..."}
    if lookup.get("status") != "Completed":
        # handle Pending / Expired / User canceled as needed
        return HttpResponse(f"Payment status is not completed: {lookup.get('status')}")

    # At this point payment is confirmed. Use purchase_order_name or purchase_order_id to find ticket_type.
    # If you stored purchase_order_id mapping to ticket_type, you should retrieve it here.
    # For simplicity, we'll encode the ticket_type id in purchase_order_name when initiating (or store mapping in DB).
    # If you did not store mapping, you can include purchase_order_id and extra meta in initiate payload merchant_extra.
    # Here, try to parse purchase_order_name if present:
    purchase_order_name = request.GET.get("purchase_order_name") or request.GET.get("purchase_order_name")
    # Alternatively, we can fetch from lookup response if it contains merchant data. For reliability you should
    # store mapping (purchase_order_id -> ticket_type_id) in DB when calling initiate_khalti.
    #
    # For a reliable flow below, we expect initiate_khalti stored a mapping in session or DB. If not, you MUST adapt.

    # --- Recommended approach: when calling initiate_khalti, save mapping to a simple model or cache:
    # e.g. PaymentOrder(purchase_order_id=..., ticket_type_id=..., phone=...)

    # For this code, I'll attempt to retrieve ticket_type by purchase_order_name heuristic (not ideal):
    po_name = lookup.get("purchase_order_name") or request.GET.get("purchase_order_name")
    ticket_type = None
    if po_name:
        # Our purchase_order_name was "Event - TicketType", try to find matching TicketType
        # This is a fallback and may need improvement for robustness
        try:
            # naive split: last part after dash is tickettype name
            if " - " in po_name:
                _, tt_name = po_name.rsplit(" - ", 1)
                ticket_type = TicketType.objects.filter(name__iexact=tt_name).order_by('id').first()
        except Exception:
            ticket_type = None

    # If still not found, fallback to first TicketType (NOT recommended)
    if ticket_type is None:
        ticket_type = TicketType.objects.first()

    if ticket_type is None:
        return HttpResponse("Ticket type not found; cannot create ticket.", status=500)

    # Create ticket only after successful verification
    # Decrement limit safely
    if ticket_type.limit is not None:
        if ticket_type.limit <= 0:
            return HttpResponse("Sold out", status=400)
        ticket_type.limit -= 1
        ticket_type.save()

    # create ticket
    ticket = Ticket.objects.create(
        ticket_type=ticket_type,
        purchaser_phone=lookup.get("mobile") or "",  # mobile returned by callback/lookup
        payment_status="PAID" if lookup.get("status") == "Completed" else "PENDING",
        khalti_ref=lookup.get("transaction_id") or lookup.get("tidx") or "",
        status="VALID"
    )

    # Generate a unique QR (use ticket.id and secret HMAC if you want)
    qr_payload = str(ticket.id)
    qr_img = qrcode.make(qr_payload)
    qr_io = BytesIO()
    qr_img.save(qr_io, format='PNG')
    qr_io.seek(0)
    ticket.qr_image.save(f"ticket_{ticket.id}.png", File(qr_io))

    # Generate PDF receipt (reportlab) and embed QR
    pdf_io = BytesIO()
    c = canvas.Canvas(pdf_io, pagesize=A4)

    # Simple layout (you can design nicer)
    x = 50
    y = 800
    c.setFont("Helvetica-Bold", 16)
    c.drawString(x, y, "MeroTicket - Receipt")
    c.setFont("Helvetica", 12)
    y -= 30
    c.drawString(x, y, f"Ticket ID: {ticket.id}")
    y -= 20
    c.drawString(x, y, f"Event: {ticket.ticket_type.event.name}")
    y -= 20
    c.drawString(x, y, f"Ticket Type: {ticket.ticket_type.name}")
    y -= 20
    c.drawString(x, y, f"Amount (Rs): {ticket.ticket_type.price}")
    y -= 30

    # draw QR - use ImageReader
    qr_io.seek(0)
    qr_reader = ImageReader(qr_io)
    c.drawImage(qr_reader, x, y-160, width=150, height=150)  # QR on the left

    c.showPage()
    c.save()
    pdf_io.seek(0)
    ticket.receipt_pdf.save(f"receipt_{ticket.id}.pdf", File(pdf_io))

    ticket.save()

    # redirect to success page
    return redirect('ticket_success', ticket_id=ticket.id)


# ---------------------------------------------------------
# 4) Ticket success view
# ---------------------------------------------------------
def ticket_success(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    return render(request, 'ticket/success.html', {'ticket': ticket})'''

logger = logging.getLogger("ticket")


'''def buy_ticket(request, tickettype_id):
    ticket_type = get_object_or_404(TicketType, id=tickettype_id)
    logger.debug("Rendering checkout for TicketType id=%s name=%s", ticket_type.id, ticket_type.name)
    return render(request, 'ticket/checkout.html', {
        'ticket_type': ticket_type,
        'KHALTI_PUBLIC_KEY': settings.KHALTI_PUBLIC_KEY,
    })'''
def buy_ticket(request, tickettype_id):
    ticket_type = get_object_or_404(TicketType, id=tickettype_id)

    request.session["selected_ticket_type_id"] = ticket_type.id

    logger.debug("Rendering checkout for TicketType id=%s name=%s", ticket_type.id, ticket_type.name)

    return render(request, 'ticket/checkout.html', {
        'ticket_type': ticket_type,
        'KHALTI_PUBLIC_KEY': settings.KHALTI_PUBLIC_KEY,
    })



@csrf_exempt
def initiate_khalti(request):
    logger.debug("initiate_khalti called, method=%s", request.method)

    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        payload = json.loads(request.body)
        # ticket_type_id = payload.get("ticket_type_id")
        ticket_type_id = request.session.get("selected_ticket_type_id") or payload.get("ticket_type_id")

        name = payload.get("name")   # ← ADDED
        phone = payload.get("phone")
        
        logger.debug("Initiate payload: ticket_type_id=%s name=%s phone=%s",
                     ticket_type_id, name, phone)

        if not ticket_type_id or not name or not phone:
            return JsonResponse(
                {"error": "Missing required fields (ticket_type_id, name, phone)"},
                status=400
            )

        ticket_type = TicketType.objects.get(id=ticket_type_id)

    except Exception as e:
        logger.exception("Bad payload or missing TicketType: %s", e)
        return JsonResponse({"error": "Invalid payload or ticket type", "details": str(e)}, status=400)

    # ------------------------------------
    # Generate purchase order ID
    # ------------------------------------
    purchase_order_id = f"ORDER-{uuid.uuid4().hex[:12]}"
    return_url = request.build_absolute_uri(reverse('khalti_callback'))

    # ------------------------------------
    # Payload for Khalti API
    # ------------------------------------
    initiate_payload = {
        "return_url": return_url,
        "website_url": request.build_absolute_uri('/'),
        "amount": int(ticket_type.price * 100),     # in paisa
        "purchase_order_id": purchase_order_id,
        "purchase_order_name": f"{ticket_type.event.name} - {ticket_type.name}",
        "customer_info": {
            "name": name,       # ← ADDED
            "phone": phone      # REQUIRED
        }
    }

    headers = {
        "Authorization": f"Key {settings.KHALTI_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    logger.debug("Calling Khalti initiate with url=%s payload=%s",
                 settings.KHALTI_INITIATE_URL, initiate_payload)

    # ------------------------------------
    # Call Khalti API
    # ------------------------------------
    try:
        resp = requests.post(settings.KHALTI_INITIATE_URL,
                             json=initiate_payload,
                             headers=headers,
                             timeout=20)

        logger.debug("Khalti /initiate response status=%s", resp.status_code)

        try:
            resp_json = resp.json()
        except Exception as e:
            logger.exception("Failed to parse JSON from Khalti initiate: %s", e)
            resp_json = {"error": "invalid_json_response", "raw": resp.text}

        logger.debug("Khalti /initiate response json: %s", resp_json)

        # ------------------------------------
        # Save PaymentOrder mapping (RECOMMENDED)
        # ------------------------------------
        from .models import PaymentOrder
        PaymentOrder.objects.create(
            purchase_order_id=purchase_order_id,
            ticket_type=ticket_type,
            name=name,
            phone=phone,
            raw_response=resp_json
        )

        return JsonResponse(resp_json)

    except requests.RequestException as e:
        logger.exception("Network error during Khalti initiate: %s", e)
        return JsonResponse({"error": "Failed to contact Khalti", "details": str(e)}, status=500)



def khalti_callback(request):
    logger.debug("khalti_callback called with GET params: %s", request.GET.dict())
    pidx = request.GET.get("pidx")
    status = request.GET.get("status")
    purchase_order_id = request.GET.get("purchase_order_id") or request.GET.get("purchase_order_id")
    if not pidx:
        logger.error("Missing pidx in callback")
        return HttpResponseBadRequest("Missing pidx")

    headers = {"Authorization": f"Key {settings.KHALTI_SECRET_KEY}", "Content-Type": "application/json"}
    lookup_payload = {"pidx": pidx}
    logger.debug("Calling Khalti lookup with payload: %s", lookup_payload)
    try:
        r = requests.post(settings.KHALTI_VERIFY_URL, json=lookup_payload, headers=headers, timeout=20)
        r.raise_for_status()
        lookup = r.json()
        logger.debug("Khalti lookup response: %s", lookup)
    except requests.RequestException as e:
        logger.exception("Khalti lookup failed: %s", e)
        return HttpResponse("Error verifying payment with Khalti: " + str(e), status=500)

    if lookup.get("status") != "Completed":
        logger.warning("Payment not completed: status=%s lookup=%s", lookup.get("status"), lookup)
        return HttpResponse(f"Payment status not completed: {lookup.get('status')}")

    # find PaymentOrder record (recommended)
    try:
        from .models import PaymentOrder
        po = PaymentOrder.objects.filter(purchase_order_id=lookup.get("purchase_order_id")).first()
        if po:
            ticket_type = po.ticket_type
            phone = po.phone
        else:
            # fallback: try purchase_order_name from lookup if present
            po_name = lookup.get("purchase_order_name") or lookup.get("purchase_order_name")
            ticket_type = None
            if po_name and " - " in po_name:
                _, tt_name = po_name.rsplit(" - ", 1)
                ticket_type = TicketType.objects.filter(name__iexact=tt_name).first()
            if ticket_type is None:
                # use session stored value, not default Early Bird
                fallback_id = request.session.get("selected_ticket_type_id")
            if fallback_id:
                ticket_type = TicketType.objects.get(id=fallback_id)
                phone = lookup.get("mobile") or ""
            
    except Exception as e:
        logger.exception("Failed to resolve ticket_type from PaymentOrder: %s", e)
        return HttpResponse("Internal error", status=500)

    if ticket_type.limit is not None:
        if ticket_type.limit <= 0:
            logger.warning("Ticket type sold out for id=%s", ticket_type.id)
            return HttpResponse("Sold out", status=400)
        ticket_type.limit -= 1
        ticket_type.save()

    # create ticket
    ticket = Ticket.objects.create(
        ticket_type=ticket_type,
        purchaser_phone=lookup.get("mobile") or phone or "",
        payment_status="PAID",
        khalti_ref=lookup.get("transaction_id") or lookup.get("tidx") or "",
        status="VALID"
    )

    # generate qr
    try:
        qr_payload = str(ticket.id)
        qr_img = qrcode.make(qr_payload)
        qr_io = BytesIO()
        qr_img.save(qr_io, format='PNG')
        qr_io.seek(0)
        ticket.qr_image.save(f"ticket_{ticket.id}.png", File(qr_io))
    except Exception as e:
        logger.exception("Failed generating QR: %s", e)

    # generate PDF
    try:
        pdf_io = BytesIO()
        c = canvas.Canvas(pdf_io, pagesize=A4)
        x = 50
        y = 800
        c.setFont("Helvetica-Bold", 16)
        c.drawString(x, y, "MeroTicket - Receipt")
        c.setFont("Helvetica", 12)
        y -= 30
        c.drawString(x, y, f"Ticket ID: {ticket.id}")
        y -= 20
        c.drawString(x, y, f"Event: {ticket.ticket_type.event.name}")
        y -= 20
        c.drawString(x, y, f"Ticket Type: {ticket.ticket_type.name}")
        y -= 20
        c.drawString(x, y, f"Amount (Rs): {ticket.ticket_type.price}")
        y -= 30
        qr_io.seek(0)
        qr_reader = ImageReader(qr_io)
        c.drawImage(qr_reader, x, y-160, width=150, height=150)
        c.save()
        pdf_io.seek(0)
        ticket.receipt_pdf.save(f"receipt_{ticket.id}.pdf", File(pdf_io))
    except Exception as e:
        logger.exception("Failed generating PDF: %s", e)

    ticket.save()
    logger.info("Ticket created id=%s for purchase_order=%s transaction=%s", ticket.id, purchase_order_id, lookup.get("transaction_id"))

    return redirect('ticket_success', ticket_id=ticket.id)


'''def ticket_success(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    logger.debug("Showing success for ticket id=%s", ticket_id)
    return render(request, 'ticket/success.html', {'ticket': ticket})'''

def ticket_success(request, ticket_id):
    ticket = Ticket.objects.get(id=ticket_id)

    # Generate QR code content (unique per ticket)
    qr_data = f"TICKET-ID:{ticket.id}"
    qr = qrcode.make(qr_data)
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    qr_image = buffer.getvalue()

    # Encode QR as base64 for template
    import base64
    qr_base64 = base64.b64encode(qr_image).decode()

    return render(request, "ticket/ticket_success.html", {
        "ticket": ticket,
        "qr_base64": qr_base64,
    })

from PIL import Image

def download_ticket_pdf(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)

    # PDF response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="ticket-{ticket.id}.pdf"'

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)

    # Load QR from ticket file
    qr_path = ticket.qr_image.path

    # Convert QR to PIL Image
    qr_img = Image.open(qr_path)

    # Wrap it for ReportLab
    qr_image_reader = ImageReader(qr_img)

    # Draw QR code
    p.drawImage(qr_image_reader, 50, 550, width=150, height=150)

    # Ticket details
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, 520, "E-Ticket Confirmation")

    p.setFont("Helvetica", 12)
    p.drawString(50, 500, f"Ticket ID: {ticket.id}")
    p.drawString(50, 480, f"Event: {ticket.ticket_type.event.name}")
    p.drawString(50, 460, f"Ticket Type: {ticket.ticket_type.name}")
    p.drawString(50, 440, f"Price: Rs. {ticket.ticket_type.price}")
    p.drawString(50, 420, f"Phone: {ticket.purchaser_phone}")

    p.showPage()
    p.save()

    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)

    return response