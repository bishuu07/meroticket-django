# ticket/views.py
import base64
from decimal import Decimal
from tkinter import Image
from django.shortcuts import render, redirect, get_object_or_404

from .fonepay_utils import generate_hmac_sha512, make_prn
from .models import FonepayQRRequest, PaymentOrder, TicketType, Ticket, Advertisement
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
from django.http import HttpResponse, JsonResponse,  HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.core.files import File
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from django.urls import reverse
from reportlab.lib.pagesizes import letter
from django.db import transaction
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import logout











'''def home(request):
    events = Event.objects.all()
    
    return render(request, 'ticket/home.html', {'events': events})'''

def home(request):
    events = Event.objects.all()
    #ad = Advertisement.objects.filter(active=True).first()  # Get the first active ad
    ads = Advertisement.objects.all()
    
    return render(request, 'ticket/home.html', {
        'events': events,
        'ads': ads,
    })

def staff_logout(request):
    logout(request)
    return redirect('login') 
    




def ticket_success(request, ticket_id):
    ticket = Ticket.objects.get(id=ticket_id)
    return render(request, 'ticket/success.html', {'ticket': ticket})



logger = logging.getLogger("ticket")

def buy_ticket(request, tickettype_id):
    """
    Display checkout page with ticket info and quantity.
    Ensures user cannot select more than remaining tickets.
    """
    ticket_type = get_object_or_404(TicketType, id=tickettype_id)

    # Get quantity from GET, default 1
    qty = int(request.GET.get("qty", 1))
    qty = max(1, qty)

    # Remaining tickets
    remaining = ticket_type.limit #- ticket_type.sold
    if remaining <= 0:
        return render(request, "ticket/sold_out.html", {
            "ticket_type": ticket_type,
            "message": "This ticket type is sold out."
        })

    # Limit quantity to remaining tickets
    if qty > remaining:
        qty = remaining

    # Total price
    total_price = ticket_type.price * qty

    # Save selected info in session for payment callback
    request.session["selected_qty"] = qty
    request.session["selected_ticket_type_id"] = tickettype_id

    return render(request, "ticket/checkout.html", {
        "ticket_type": ticket_type,
        "qty": qty,
        "max_qty": remaining,
        "total_price": total_price
    })




def initiate_khalti(request):
    logger.debug("initiate_khalti called, method=%s", request.method)

    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        payload = json.loads(request.body)

        ticket_type_id = request.session.get("selected_ticket_type_id") or payload.get("ticket_type_id")

        name = payload.get("name")
        phone = payload.get("phone")

        # ⭐ NEW: Read quantity
        qty = int(payload.get("qty", 1))
        request.session["selected_qty"] = qty

        logger.debug(
            "Initiate payload: ticket_type_id=%s name=%s phone=%s qty=%s",
            ticket_type_id, name, phone, qty
        )

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
    # Purchase Order ID
    # ------------------------------------
    purchase_order_id = f"ORDER-{uuid.uuid4().hex[:12]}"
    return_url = request.build_absolute_uri(reverse('khalti_callback'))

    # ------------------------------------
    # ⭐ FIXED AMOUNT (price × qty × 100)
    # ------------------------------------
    total_amount = int(ticket_type.price * qty * 100)

    initiate_payload = {
        "return_url": return_url,
        "website_url": request.build_absolute_uri('/'),
        "amount": total_amount,        # ⭐ CORRECT TOTAL PRICE
        "purchase_order_id": purchase_order_id,
        "purchase_order_name": f"{ticket_type.event.name} - {ticket_type.name}",
        "customer_info": {
            "name": name,
            "phone": phone
        }
    }

    headers = {
        "Authorization": f"Key {settings.KHALTI_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    logger.debug(
        "Calling Khalti initiate with url=%s payload=%s",
        settings.KHALTI_INITIATE_URL, initiate_payload
    )

    # ------------------------------------
    # Call Khalti API
    # ------------------------------------
    try:
        resp = requests.post(
            settings.KHALTI_INITIATE_URL,
            json=initiate_payload,
            headers=headers,
            timeout=20
        )

        logger.debug("Khalti /initiate response status=%s", resp.status_code)

        try:
            resp_json = resp.json()
        except Exception as e:
            logger.exception("Failed to parse JSON from Khalti initiate: %s", e)
            resp_json = {"error": "invalid_json_response", "raw": resp.text}

        logger.debug("Khalti /initiate response json: %s", resp_json)

        # Save Payment Order Mapping
        from .models import PaymentOrder
        PaymentOrder.objects.create(
            purchase_order_id=purchase_order_id,
            ticket_type=ticket_type,
            name=name,
            phone=phone,
            quantity=qty,
            raw_response=resp_json
        )

        return JsonResponse(resp_json)

    except requests.RequestException as e:
        logger.exception("Network error during Khalti initiate: %s", e)
        return JsonResponse({"error": "Failed to contact Khalti", "details": str(e)}, status=500)











logger = logging.getLogger(__name__)

def khalti_callback(request):
    logger.debug("khalti_callback called with GET params: %s", request.GET.dict())
    pidx = request.GET.get("pidx")
    if not pidx:
        logger.error("Missing pidx in callback")
        return HttpResponseBadRequest("Missing pidx")

    # Verify payment with Khalti
    headers = {
        "Authorization": f"Key {settings.KHALTI_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    try:
        r = requests.post(settings.KHALTI_VERIFY_URL, json={"pidx": pidx}, headers=headers, timeout=20)
        r.raise_for_status()
        lookup = r.json()
        logger.debug("Khalti lookup response: %s", lookup)
    except requests.RequestException as e:
        logger.exception("Khalti lookup failed")
        return HttpResponse("Error verifying payment with Khalti: " + str(e), status=500)

    if lookup.get("status") != "Completed":
        logger.warning("Payment not completed: %s", lookup.get("status"))
        return HttpResponse(f"Payment status not completed: {lookup.get('status')}")

    # ✅ Get purchase_order_id from GET first, fallback to API response
    purchase_order_id = request.GET.get("purchase_order_id")
    if not purchase_order_id:
        purchase_order_id = lookup.get("purchase_order_id") or lookup.get("data", {}).get("purchase_order_id")

    if not purchase_order_id:
        logger.error("purchase_order_id missing in Khalti lookup: %s", lookup)
        return HttpResponse("Invalid payment lookup (missing purchase_order_id)", status=400)

    # Import models
    from .models import PaymentOrder, TicketType, Ticket

    # Find PaymentOrder
    po = PaymentOrder.objects.filter(purchase_order_id=purchase_order_id).select_related("ticket_type").first()
    if not po:
        logger.error("PaymentOrder not found for purchase_order_id=%s", purchase_order_id)
        return HttpResponse("PaymentOrder not found", status=400)

    # Save raw response
    try:
        po.raw_response = lookup
        po.save(update_fields=["raw_response"])
    except Exception:
        logger.exception("Failed saving raw_response for PaymentOrder %s", po.id)

    # Atomic block to prevent overselling
    try:
        with transaction.atomic():
            tt = TicketType.objects.select_for_update().get(pk=po.ticket_type_id)

            qty = po.quantity  # number of tickets purchased

            # Check enough stock
            if tt.limit < qty:
                logger.warning(
                    "Over-attempted purchase. Remaining=%s, requested=%s",
                    tt.limit, qty
                )
                return HttpResponse("Not enough tickets remaining", status=400)

            # Deduct stock
            tt.limit -= qty
            tt.sold = (tt.sold or 0) + qty
            tt.save(update_fields=["limit", "sold"])

            # Create multiple tickets
        tickets = []
        for _ in range(qty):
            ticket = Ticket.objects.create(
                ticket_type=tt,
                purchaser_name=po.name,
                purchaser_phone=po.phone,
                payment_status="PAID",
                khalti_ref=lookup.get("transaction_id") or lookup.get("tidx") or "",
                status="VALID"
            )

            # Generate QR
            qr_payload = f"TICKET:{ticket.id}:{ticket.qr_token}"
            qr_img = qrcode.make(qr_payload)
            qr_io = BytesIO()
            qr_img.save(qr_io, format="PNG")
            qr_io.seek(0)
            ticket.qr_image.save(f"ticket_{ticket.id}.png", File(qr_io), save=False)

            # Generate PDF receipt
            try:
                pdf_io = BytesIO()
                c = canvas.Canvas(pdf_io, pagesize=A4)

                x, y = 50, 800

                # Event Logo
                event_logo = ticket.ticket_type.event.image
                if event_logo:
                    try:
                        c.drawImage(event_logo.path, x, y - 80, width=120, height=120, preserveAspectRatio=True, mask='auto')
                        y -= 140
                    except:
                        pass

                # Title
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

                # QR
                y -= 30
                qr_io.seek(0)
                qr_reader = ImageReader(qr_io)
                c.drawImage(qr_reader, x, y - 160, width=150, height=150)

                c.save()
                pdf_io.seek(0)
                ticket.receipt_pdf.save(f"receipt_{ticket.id}.pdf", File(pdf_io), save=False)

            except Exception as e:
                logger.exception("PDF failed for ticket %s", ticket.id)

            ticket.save()
            tickets.append(ticket)   # NOW INSIDE LOOP


    except TicketType.DoesNotExist:
        logger.exception("TicketType not found for PaymentOrder %s", po.id)
        return HttpResponse("TicketType not found", status=500)
    except Exception as e:
        logger.exception(
            "Error while processing payment callback for purchase_order=%s: %s",
            purchase_order_id, e
        )
        return HttpResponse("Internal server error", status=500)

    # Redirect to single or multi-ticket success page
    if len(tickets) == 1:
        return redirect("ticket_success", ticket_id=tickets[0].id)

    return render(request, "ticket/multi_success.html", {"tickets": tickets})



'''def download_ticket_pdf(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="ticket-{ticket.id}.pdf"'

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)

    # Load QR path directly into ImageReader
    qr_path = ticket.qr_image.path
    qr_image_reader = ImageReader(qr_path)

    # Draw QR
    p.drawImage(qr_image_reader, 50, 550, width=150, height=150)

    # Ticket Details
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

    return response'''
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from .models import Ticket

def download_ticket_png(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)

    # Create a white canvas (PNG image)
    width, height = 800, 1000
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    # Load fonts (PIL default font used if custom not found)
    try:
        title_font = ImageFont.truetype("arial.ttf", 36)
        text_font = ImageFont.truetype("arial.ttf", 28)
    except:
        title_font = ImageFont.load_default()
        text_font = ImageFont.load_default()

    # ---- LOAD QR IMAGE ----
    qr_img = Image.open(ticket.qr_image.path).resize((250, 250))
    image.paste(qr_img, (50, 50))

    # ---- ADD TEXT ----
    draw.text((50, 330), "E-Ticket Confirmation", font=title_font, fill="black")

    draw.text((50, 400), f"Ticket ID: {ticket.id}", font=text_font, fill="black")
    draw.text((50, 450), f"Event: {ticket.ticket_type.event.name}", font=text_font, fill="black")
    draw.text((50, 500), f"Ticket Type: {ticket.ticket_type.name}", font=text_font, fill="black")
    draw.text((50, 550), f"Price: Rs. {ticket.ticket_type.price}", font=text_font, fill="black")
    draw.text((50, 600), f"Phone: {ticket.purchaser_phone}", font=text_font, fill="black")

    # ---- EXPORT PNG ----
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)

    response = HttpResponse(buffer, content_type="image/png")
    response["Content-Disposition"] = f'attachment; filename="ticket-{ticket.id}.png"'

    return response





def ticket_success(request, ticket_id=None):
    """
    Displays ticket(s) that were purchased.
    Supports 1 or multiple tickets.
    """

    ticket_list = []

    if ticket_id:
        # Single-ticket success
        ticket = get_object_or_404(Ticket, id=ticket_id)
        ticket_list = [ticket]
    else:
        # Multiple tickets: get stored list
        ticket_ids = request.session.get("recent_tickets", [])
        ticket_list = Ticket.objects.filter(id__in=ticket_ids)

    ticket_data = []

    for ticket in ticket_list:
        # Generate QR
        qr_payload = f"TICKET:{ticket.id}:{ticket.qr_token}"
        qr_img = qrcode.make(qr_payload)

        buffer = BytesIO()
        qr_img.save(buffer, format="PNG")
        qr_b64 = base64.b64encode(buffer.getvalue()).decode()

        ticket_data.append({
            "ticket": ticket,
            "qr_base64": qr_b64
        })

    return render(request, "ticket/ticket_success.html", {
        "ticket_data": ticket_data  # 👈 IMPORTANT: Your template expects this
    })


def staff_required(view_func):
    return user_passes_test(lambda u: u.is_active and u.is_staff)(view_func)


@staff_required
@login_required
def scanner_page(request):
    """
    Renders the scanning page (camera + JS).
    Only staff users can access.
    """
    # Extra safety: if someone reaches the page while not staff, block
    if not request.user.is_staff:
        return HttpResponseForbidden("You are not authorized to access the scanner.")

    return render(request, "ticket/scan.html")

import json

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from django.shortcuts import render, get_object_or_404

from .models import Ticket, ScanLog
@require_POST
@login_required
@user_passes_test(lambda u: u.is_active and u.is_staff)
def verify_ticket(request):
    """
    POST JSON: { "qr_data": "<payload>" }
    Returns JSON with status: valid / used / invalid and helpful fields.
    """
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"status": "invalid", "message": "Invalid JSON"}, status=400)

    qr_data = data.get("qr_data")
    if not qr_data:
        return JsonResponse({"status": "invalid", "message": "No QR data provided"}, status=400)

    # Expected format: "TICKET:<ticket_id>:<qr_token>"
    try:
        parts = qr_data.split(":")
        if len(parts) == 3 and parts[0] == "TICKET":
            ticket_id = parts[1]
            qr_token = parts[2]
        else:
            return JsonResponse({"status": "invalid", "message": "Bad QR format"}, status=400)
    except Exception:
        return JsonResponse({"status": "invalid", "message": "Bad QR format"}, status=400)

    # Lookup ticket (we'll lock row for safe concurrent access)
    try:
        with transaction.atomic():
            ticket = Ticket.objects.select_for_update().get(id=ticket_id, qr_token=qr_token)

            # Check payment status
            if ticket.payment_status != "PAID":
                ScanLog.objects.create(ticket=ticket, staff=request.user, result="not_paid")
                return JsonResponse({"status": "invalid", "message": "Payment not completed"}, status=400)

            # Check validity window
            tt = ticket.ticket_type
            now = timezone.now()
            if tt.valid_from and now < tt.valid_from:
                ScanLog.objects.create(ticket=ticket, staff=request.user, result="too_early")
                return JsonResponse({"status": "invalid", "message": "Ticket not yet valid"}, status=400)
            if tt.valid_until and now > tt.valid_until:
                ScanLog.objects.create(ticket=ticket, staff=request.user, result="expired")
                return JsonResponse({"status": "invalid", "message": "Ticket expired"}, status=400)

            # If already used
            if ticket.status == "USED":
                ScanLog.objects.create(ticket=ticket, staff=request.user, result="already_used")
                return JsonResponse({"status": "used", "message": "Ticket already used"}, status=200)

            # Mark as used
            ticket.status = "USED"
            ticket.used_time = timezone.now()
            ticket.used_by = request.user
            ticket.save()

            # Log success
            ScanLog.objects.create(ticket=ticket, staff=request.user, result="valid")

    except Ticket.DoesNotExist:
        return JsonResponse({"status": "invalid", "message": "Ticket not found"}, status=404)
    except Exception as e:
        # Unexpected error
        return JsonResponse({"status": "invalid", "message": f"Server error: {str(e)}"}, status=500)

    # Return success details to front-end
    return JsonResponse({
        "status": "valid",
        "ticket_id": str(ticket.id),
        "event": ticket.ticket_type.event.name,
        "type": ticket.ticket_type.name,
        "message": "Ticket verified. Entry allowed."
    }, status=200)

@login_required
def user_dashboard(request):
    tickets = request.user.ticket_set.all()  # if users are linked
    return render(request, "ticket/dashboard.html", {"tickets": tickets})



logger = logging.getLogger(__name__)

# Endpoint: POST -> initiate_fonepay
'''@csrf_exempt
def initiate_fonepay(request):
    """
    Expects JSON POST:
    {
      "ticket_type_id": <int>,
      "qty": <int>,
      "remarks1": "EventName - seat" (optional),
      "remarks2": "extra" (optional)
    }
    Returns JSON with qrMessage and thirdpartyQrWebSocketUrl on success.


    """
    


    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        payload = json.loads(request.body)
    except Exception as e:
        logger.exception("Bad JSON in initiate_fonepay")
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    ticket_type = int(payload.get("ticket_type_id")) or request.session.get("selected_ticket_type_id")
    qty = int(payload.get("qty", request.session.get("selected_qty", 1)))
    # Ensure remarks are NEVER empty
    remarks1 = ticket_type.event.name[:30]
    remarks2 = ticket_type.name[:30]


    if not ticket_type:
        return JsonResponse({"error": "Missing ticket_type_id"}, status=400)

    try:
        tt = TicketType.objects.get(pk=ticket_type)
    except TicketType.DoesNotExist:
        return JsonResponse({"error": "TicketType not found"}, status=404)

    # amount in decimal (as in docs, string numeric allowed). Using ticket price × qty
    amount = int(ticket_type.price * qty)
    amount_str = str(amount)


    # Create PRN
    prn = make_prn()

    # HMAC message: AMOUNT,PRN,MERCHANT-CODE,REMARKS1,REMARKS2
    # NOTE: per docs, values must not be URL-encoded and separated by commas
    message = f"{amount_str},{prn},{settings.FONEPAY_MERCHANT_CODE},{remarks1},{remarks2}"

    dv = generate_hmac_sha512(settings.FONEPAY_SECRET_KEY, message)

    request_payload = {
    "amount": amount_str,
    "remarks1": remarks1,
    "remarks2": remarks2,
    "prn": prn,
    "merchantCode": settings.FONEPAY_MERCHANT_CODE,
    "dataValidation": dv,
    "username": settings.FONEPAY_USERNAME,
    "password": settings.FONEPAY_PASSWORD,
}
    logger.error("DEBUG-FP | Payload sent to FonePay: %s", request_payload)
    logger.error("DEBUG-FP | DV message: %s", message)
    logger.error("DEBUG-FP | DV generated: %s", dv)

    api_url = f"{settings.FONEPAY_API_BASE}/merchant/merchantDetailsForThirdParty/thirdPartyDynamicQrDownload"
    logger.debug("Calling FonePay QR API %s payload=%s", api_url, request_payload)
    logger.error("DEBUG-FP | URL: %s", api_url)

    try:
        resp = requests.post(api_url, json=request_payload, timeout=20)
        resp.raise_for_status()
        resp_json = resp.json()
    except requests.RequestException as e:
        logger.exception("Network error calling FonePay thirdPartyDynamicQrDownload")
        return JsonResponse({"error": "Failed contacting FonePay", "details": str(e)}, status=502)
    except Exception as e:
        logger.exception("Invalid JSON from FonePay")
        return JsonResponse({"error": "Invalid response from FonePay", "details": str(e)}, status=502)

    # Save mapping record
    # Optionally link to PaymentOrder if you created one earlier. We'll create PaymentOrder now to keep parity with Khalti flow.
    purchase_order_id = f"FONEPAY-{prn}"
    po = PaymentOrder.objects.create(
        purchase_order_id=purchase_order_id,
        ticket_type=tt,
        name=payload.get("name", ""),
        phone=payload.get("phone", ""),
        quantity=qty,
        raw_response=resp_json
    )

    FonepayQRRequest.objects.create(
        prn=prn,
        payment_order=po,
        amount=amount,
        remarks1=request_payload["remarks1"],
        remarks2=request_payload["remarks2"],
        raw_response=resp_json
    )

    # Return important fields to front-end
    result = {
        "success": resp_json.get("success", True),
        "qrMessage": resp_json.get("qrMessage"),
        "thirdpartyQrWebSocketUrl": resp_json.get("thirdpartyQrWebSocketUrl"),
        "prn": prn,
        "payment_order_id": purchase_order_id,
    }
    logger.debug("Fonepay QR created: prn=%s response=%s", prn, result)
    return JsonResponse(result)'''
@csrf_exempt
def initiate_fonepay(request):
    """
    Expected POST JSON:
    {
        "ticket_type_id": <int>,
        "qty": <int>,
        "name": "...",
        "phone": "..."
    }
    Returns FonePay Dynamic QR JSON.
    """

    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    # -------------------------
    # Parse JSON
    # -------------------------
    try:
        payload = json.loads(request.body)
    except Exception:
        logger.exception("Bad JSON in initiate_fonepay")
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    # -------------------------
    # Extract required fields
    # -------------------------
    ticket_type_id = payload.get("ticket_type_id")
    qty = int(payload.get("qty", 1))

    if not ticket_type_id:
        return JsonResponse({"error": "Missing ticket_type_id"}, status=400)

    # -------------------------
    # Fetch TicketType object
    # -------------------------
    try:
        tt = TicketType.objects.get(pk=int(ticket_type_id))
    except TicketType.DoesNotExist:
        return JsonResponse({"error": "TicketType not found"}, status=404)

    # -------------------------
    # Prepare remarks
    # -------------------------
    remarks1 = tt.event.name[:30]
    remarks2 = tt.name[:30]

    # -------------------------
    # Price calculation
    # (FonePay requires integer amount)
    # -------------------------
    amount = int(tt.price * qty)
    amount_str = str(amount)

    # -------------------------
    # Generate PRN + DV
    # -------------------------
    prn = make_prn()  # 32-char code

    # DV message
    dv_message = (
        f"{amount_str},{prn},{settings.FONEPAY_MERCHANT_CODE},{remarks1},{remarks2}"
    )

    dv = generate_hmac_sha512(settings.FONEPAY_SECRET_KEY, dv_message)

    # -------------------------
    # Build payload for FonePay
    # -------------------------
    request_payload = {
        "amount": amount_str,
        "remarks1": remarks1,
        "remarks2": remarks2,
        "prn": prn,
        "merchantCode": settings.FONEPAY_MERCHANT_CODE,
        "dataValidation": dv,
        "username": settings.FONEPAY_USERNAME,
        "password": settings.FONEPAY_PASSWORD,
    }

    api_url = (
        f"{settings.FONEPAY_API_BASE}/merchant/merchantDetailsForThirdParty/thirdPartyDynamicQrDownload"
    )

    # -------------------------
    # Debug Logs
    # -------------------------
    logger.error("DEBUG-FP | Payload sent to FonePay: %s", request_payload)
    logger.error("DEBUG-FP | DV message: %s", dv_message)
    logger.error("DEBUG-FP | DV generated: %s", dv)
    logger.error("DEBUG-FP | URL: %s", api_url)

    # -------------------------
    # API CALL
    # -------------------------
    try:
        resp = requests.post(api_url, json=request_payload, timeout=20)
        resp.raise_for_status()
        resp_json = resp.json()
    except requests.RequestException as e:
        logger.exception("Network error calling FonePay API")
        return JsonResponse(
            {"error": "Failed contacting FonePay", "details": str(e)}, status=502
        )
    except Exception as e:
        logger.exception("Invalid JSON from FonePay")
        return JsonResponse(
            {"error": "Invalid response from FonePay", "details": str(e)}, status=502
        )

    # -------------------------
    # Save Payment Order
    # -------------------------
    purchase_order_id = f"FONEPAY-{prn}"

    po = PaymentOrder.objects.create(
        purchase_order_id=purchase_order_id,
        ticket_type=tt,
        name=payload.get("name", ""),
        phone=payload.get("phone", ""),
        quantity=qty,
        raw_response=resp_json,
    )

    FonepayQRRequest.objects.create(
        prn=prn,
        payment_order=po,
        amount=amount,
        remarks1=remarks1,
        remarks2=remarks2,
        raw_response=resp_json,
    )

    # -------------------------
    # Return final response
    # -------------------------
    result = {
        "success": resp_json.get("success", True),
        "qrMessage": resp_json.get("qrMessage"),
        "thirdpartyQrWebSocketUrl": resp_json.get("thirdpartyQrWebSocketUrl"),
        "prn": prn,
        "payment_order_id": purchase_order_id,
    }

    logger.debug("FonePay QR created: prn=%s response=%s", prn, result)

    return JsonResponse(result)



# Endpoint: POST -> check_fonepay_qr_status
@csrf_exempt
def check_fonepay_qr_status(request):
    """
    POST JSON:
      { "prn": "<prn>" }
    Returns payment status: success / failed / pending
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    try:
        j = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    prn = j.get("prn")
    if not prn:
        return JsonResponse({"error": "Missing prn"}, status=400)

    # Build DV: PRN,MERCHANT-CODE
    message = f"{prn},{settings.FONEPAY_MERCHANT_CODE}"
    dv = generate_hmac_sha512(settings.FONEPAY_SECRET_KEY, message)

    api_url = f"{settings.FONEPAY_API_BASE}/merchant/merchantDetailsForThirdParty/thirdPartyDynamicQrGetStatus"
    payload = {
        "prn": prn,
        "merchantCode": settings.FONEPAY_MERCHANT_CODE,
        "dataValidation": dv,
        "username": settings.FONEPAY_USERNAME,
        "password": settings.FONEPAY_PASSWORD,
    }

    try:
        resp = requests.post(api_url, json=payload, timeout=20)
        resp.raise_for_status()
        status_json = resp.json()
    except requests.RequestException as e:
        logger.exception("Network error checking FonePay QR status")
        return JsonResponse({"error": "Failed contacting FonePay", "details": str(e)}, status=502)

    # Example successful response contains: {"paymentStatus":"success","prn":...}
    logger.debug("FonePay status for prn=%s -> %s", prn, status_json)

    payment_status = status_json.get("paymentStatus") or status_json.get("payment_status") or status_json.get("paymentStatus".lower())
    # normalize
    if payment_status:
        payment_status = payment_status.lower()

    # Save raw_response to our record if exists
    try:
        req = FonepayQRRequest.objects.filter(prn=prn).first()
        if req:
            req.raw_response = status_json
            req.save(update_fields=["raw_response"])
    except Exception:
        logger.exception("Failed saving raw_response for FonepayQRRequest %s", prn)

    return JsonResponse({"prn": prn, "paymentStatus": payment_status or "unknown", "raw": status_json})


