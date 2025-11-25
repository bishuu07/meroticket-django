# ticket/views.py
import base64
from tkinter import Image
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
from django.db import transaction










def home(request):
    events = Event.objects.all()
    return render(request, 'ticket/home.html', {'events': events})
    

'''def purchase_ticket(request, ticket_type_id):
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
    
    return render(request, 'ticket/purchase.html', {'ticket_type': ticket_type})'''

'''def purchase_ticket(request, ticket_type_id):
    ticket_type = TicketType.objects.get(id=ticket_type_id)

    # quantity selected
    qty = int(request.GET.get("qty", 1))

    # Check availability
    if ticket_type.sold + qty > ticket_type.limit:
        return render(request, "ticket/sold_out.html", {
            "ticket_type": ticket_type,
            "message": f"Only {ticket_type.limit - ticket_type.sold} tickets left."
        })

    if request.method == "POST":
        phone = request.POST.get("phone")

        created_tickets = []

        for i in range(qty):
            ticket = Ticket.objects.create(
                ticket_type=ticket_type,
                purchaser_phone=phone,
                payment_status="PAID",
                status="VALID"
            )

            # update counter
            ticket_type.sold += 1

            # generate QR
            qr_code_data = f"{ticket.id}-{get_random_string(10)}"
            qr_img = qrcode.make(qr_code_data)
            buffer = BytesIO()
            qr_img.save(buffer, 'PNG')
            ticket.qr_image.save(f'{ticket.id}.png', File(buffer))
            ticket.save()

            created_tickets.append(ticket)

        ticket_type.save()

        # If user buys many tickets, show them a list
        if len(created_tickets) > 1:
            return render(request, "ticket/multi_success.html", {
                "tickets": created_tickets
            })

        # otherwise redirect to single ticket page
        return redirect("ticket_success", ticket_id=created_tickets[0].id)

    return render(request, "ticket/purchase.html", {
        "ticket_type": ticket_type,
        "qty": qty
    })'''



def ticket_success(request, ticket_id):
    ticket = Ticket.objects.get(id=ticket_id)
    return render(request, 'ticket/success.html', {'ticket': ticket})



logger = logging.getLogger("ticket")
'''def buy_ticket(request, tickettype_id):
    ticket_type = get_object_or_404(TicketType, id=tickettype_id)

    request.session["selected_ticket_type_id"] = ticket_type.id

    logger.debug("Rendering checkout for TicketType id=%s name=%s", ticket_type.id, ticket_type.name)

    return render(request, 'ticket/checkout.html', {
        'ticket_type': ticket_type,
        'KHALTI_PUBLIC_KEY': settings.KHALTI_PUBLIC_KEY,
    })'''
'''def buy_ticket(request, tickettype_id):
    ticket_type = get_object_or_404(TicketType, id=tickettype_id)

    #qty = int(request.GET.get("qty", 1))  # ← get quantity
    qty = int(request.session.get("selected_qty", 1))


    # Save the selected quantity in session
    request.session["selected_qty"] = qty

    return render(request, 'ticket/checkout.html', {
        'ticket_type': ticket_type,
        'qty': qty
    })'''
'''def buy_ticket(request, tickettype_id):
    ticket_type = get_object_or_404(TicketType, id=tickettype_id)

    # Always get quantity directly from GET (from the form)
    qty = int(request.GET.get("qty", 1))

    # Save the selected quantity properly
    request.session["selected_qty"] = qty
    request.session["selected_ticket_type"] = tickettype_id  # for safety

    return render(request, 'ticket/checkout.html', {
        'ticket_type': ticket_type,
        'qty': qty
    })'''

'''def buy_ticket(request, tickettype_id):
    """
    Display checkout page with ticket info and quantity.
    Total price calculated in view for safety.
    """
    ticket_type = get_object_or_404(TicketType, id=tickettype_id)

    # Get quantity from GET or default 1
    qty = int(request.GET.get("qty", 1))
    qty = max(1, qty)  # ensure minimum 1

    # Check stock availability
    if ticket_type.limit - ticket_type.sold < qty:
        remaining = ticket_type.limit - ticket_type.sold
        return render(request, "ticket/sold_out.html", {
            "ticket_type": ticket_type,
            "message": f"Only {remaining} ticket(s) left."
        })

    # Calculate total price
    total_price = ticket_type.price * qty

    # Save selected info in session for later use
    request.session["selected_qty"] = qty
    request.session["selected_ticket_type_id"] = tickettype_id

    return render(request, "ticket/checkout.html", {
        "ticket_type": ticket_type,
        "qty": qty,
        "total_price": total_price
    })
'''
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
    remaining = ticket_type.limit - ticket_type.sold
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


'''@csrf_exempt
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
        return JsonResponse({"error": "Failed to contact Khalti", "details": str(e)}, status=500)'''

'''def initiate_khalti(request):
    logger.debug("initiate_khalti called, method=%s", request.method)

    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        payload = json.loads(request.body)

        # Ticket type from session or payload
        ticket_type_id = request.session.get("selected_ticket_type_id") or payload.get("ticket_type_id")

        name = payload.get("name")
        phone = payload.get("phone")

        # ✅ NEW: Get quantity from payload or default to 1
        qty = int(payload.get("qty", 1))
        request.session["selected_qty"] = qty  # store quantity in session

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
        "amount": int(ticket_type.price * 100),  # in paisa
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
            raw_response=resp_json
        )

        return JsonResponse(resp_json)

    except requests.RequestException as e:
        logger.exception("Network error during Khalti initiate: %s", e)
        return JsonResponse({"error": "Failed to contact Khalti", "details": str(e)}, status=500)'''

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





'''def khalti_callback(request):
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

    return redirect('ticket_success', ticket_id=ticket.id)'''


'''def ticket_success(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    logger.debug("Showing success for ticket id=%s", ticket_id)
    return render(request, 'ticket/success.html', {'ticket': ticket})'''

logger = logging.getLogger(__name__)

'''def khalti_callback(request):
    logger.debug("khalti_callback called with GET params: %s", request.GET.dict())
    pidx = request.GET.get("pidx")
    if not pidx:
        logger.error("Missing pidx in callback")
        return HttpResponseBadRequest("Missing pidx")

    # Verify with Khalti
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

    # Expect Completed status from Khalti
    if lookup.get("status") != "Completed":
        logger.warning("Payment not completed: %s", lookup.get("status"))
        return HttpResponse(f"Payment status not completed: {lookup.get('status')}")

    purchase_order_id = lookup.get("purchase_order_id")
    if not purchase_order_id:
        logger.error("purchase_order_id missing in Khalti lookup: %s", lookup)
        return HttpResponse("Invalid payment lookup (missing purchase_order_id)", status=400)

    # Import models locally to avoid circular imports if any
    from .models import PaymentOrder, TicketType, Ticket

    # Find PaymentOrder and ensure it exists
    po = PaymentOrder.objects.filter(purchase_order_id=purchase_order_id).select_related("ticket_type").first()
    if not po:
        logger.error("PaymentOrder not found for purchase_order_id=%s", purchase_order_id)
        return HttpResponse("PaymentOrder not found", status=400)

    # Save raw response for auditing
    try:
        po.raw_response = lookup
        po.save(update_fields=["raw_response"])
    except Exception:
        logger.exception("Failed saving raw_response for PaymentOrder %s", po.id)

    # Use a transaction and select_for_update to avoid overselling
    try:
        with transaction.atomic():
            # Lock the ticket_type row
            tt = TicketType.objects.select_for_update().get(pk=po.ticket_type_id)

            # Check remaining limit (your semantics: limit = remaining capacity)
            if tt.limit is None:
                logger.error("TicketType.limit is None for id=%s", tt.id)
                return HttpResponse("TicketType not configured properly", status=500)

            if tt.limit <= 0:
                logger.info("Sold out: TicketType id=%s name=%s", tt.id, tt.name)
                return HttpResponse("Sold Out", status=400)

            # Update stock: decrement limit, increment sold
            tt.limit -= 1
            tt.sold = (tt.sold or 0) + 1
            tt.save(update_fields=["limit", "sold"])

            # Create Ticket
            purchaser_phone = po.phone or lookup.get("mobile") or ""
            ticket = Ticket.objects.create(
                ticket_type=tt,
                purchaser_phone=purchaser_phone,
                payment_status="PAID",
                khalti_ref=lookup.get("transaction_id") or lookup.get("tidx") or "",
                status="VALID",
            )

            # Generate QR image and attach to ticket.qr_image
            try:
                qr_payload = f"TICKET-ID:{ticket.id}"
                qr_img = qrcode.make(qr_payload)
                qr_io = BytesIO()
                qr_img.save(qr_io, format="PNG")
                qr_io.seek(0)
                ticket.qr_image.save(f"ticket_{ticket.id}.png", File(qr_io), save=False)
            except Exception:
                logger.exception("Failed generating QR for ticket id=%s", ticket.id)

            # Generate PDF receipt and attach to ticket.receipt_pdf
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
                # price might be Decimal; convert to string
                c.drawString(x, y, f"Amount (Rs): {ticket.ticket_type.price}")
                y -= 30

                # Reuse QR image saved above (or qr_io if still available)
                # If qr_io not available, regenerate minimal QR
                try:
                    qr_io.seek(0)
                    qr_reader = ImageReader(qr_io)
                except Exception:
                    # regenerate
                    qr_img2 = qrcode.make(f"TICKET-ID:{ticket.id}")
                    qr_io2 = BytesIO()
                    qr_img2.save(qr_io2, format="PNG")
                    qr_io2.seek(0)
                    qr_reader = ImageReader(qr_io2)

                c.drawImage(qr_reader, x, y - 160, width=150, height=150)
                c.save()
                pdf_io.seek(0)
                ticket.receipt_pdf.save(f"receipt_{ticket.id}.pdf", File(pdf_io), save=False)
            except Exception:
                logger.exception("Failed generating PDF for ticket id=%s", ticket.id)

            # Save ticket with attachments
            ticket.save()

            logger.info(
                "Ticket created id=%s for purchase_order=%s khalti_ref=%s",
                ticket.id,
                purchase_order_id,
                ticket.khalti_ref,
            )

    except TicketType.DoesNotExist:
        logger.exception("TicketType not found for PaymentOrder %s", po.id)
        return HttpResponse("TicketType not found", status=500)
    except Exception as e:
        logger.exception("Error while processing payment callback for purchase_order=%s: %s", purchase_order_id, e)
        return HttpResponse("Internal server error", status=500)

    # Redirect to success page
    return redirect("ticket_success", ticket_id=ticket.id)

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

from PIL import Image'''

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
                    purchaser_phone=po.phone,
                    payment_status="PAID",
                    khalti_ref=lookup.get("transaction_id") or lookup.get("tidx") or "",
                    status="VALID"
                )

                # Generate unique QR code
                qr_payload = f"TICKET-ID:{ticket.id}-{ticket.qr_token}"
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
                    ticket.receipt_pdf.save(f"receipt_{ticket.id}.pdf", File(pdf_io), save=False)
                except Exception:
                    logger.exception("Failed generating PDF for ticket id=%s", ticket.id)

                ticket.save()
                tickets.append(ticket)

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

'''def ticket_success(request, ticket_id=None):
    """
    Displays ticket(s) purchased successfully.
    Handles single-ticket (ticket_id provided) or multi-ticket (list in session).
    """

    tickets = []

    if ticket_id:
        # Single ticket
        ticket = get_object_or_404(Ticket, id=ticket_id)
        tickets.append(ticket)
    else:
        # Multi-ticket: get list from session or query param
        ticket_ids = request.session.get("recent_tickets", [])
        tickets = Ticket.objects.filter(id__in=ticket_ids)

    # Prepare QR codes in base64 for all tickets
    qr_data_list = []
    for ticket in tickets:
        qr_payload = f"TICKET-ID:{ticket.id}-{ticket.qr_token}"
        qr_img = qrcode.make(qr_payload)
        buffer = BytesIO()
        qr_img.save(buffer, format="PNG")
        qr_image = buffer.getvalue()
        qr_base64 = base64.b64encode(qr_image).decode()
        qr_data_list.append({
            "ticket": ticket,
            "qr_base64": qr_base64
        })

    return render(request, "ticket/ticket_success.html", {
        "tickets": qr_data_list,
    })'''

'''def ticket_success(request, ticket_id=None):
    """
    Displays ticket(s) purchased successfully.
    Handles single-ticket (ticket_id provided) or multi-ticket (list in session).
    """

    tickets = []

    if ticket_id:
        # Single ticket
        ticket = get_object_or_404(Ticket, id=ticket_id)
        tickets.append(ticket)
    else:
        # Multi-ticket: get from session
        ticket_ids = request.session.get("recent_tickets", [])
        tickets = Ticket.objects.filter(id__in=ticket_ids)

    qr_data_list = []
    for ticket in tickets:
        qr_payload = f"TICKET-ID:{ticket.id}-{ticket.qr_token}"
        qr_img = qrcode.make(qr_payload)
        buffer = BytesIO()
        qr_img.save(buffer, format="PNG")
        qr_image = buffer.getvalue()
        qr_base64 = base64.b64encode(qr_image).decode()

        qr_data_list.append({
            "ticket": ticket,
            "qr_base64": qr_base64
        })

    return render(request, "ticket/ticket_success.html", {
        "tickets": qr_data_list,
    })'''

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
