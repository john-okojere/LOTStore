import base64
import binascii
import json
import logging
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Max
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from PIL import Image

from cart.models import Cart, CartItem
from shelf.models import Product, Sizes
from .forms import MockupViewForm
from .models import DesignAsset, DesignMessage, DesignQuote, DesignRequest, DesignVersion, ProductMockupView

logger = logging.getLogger(__name__)
MAX_ASSET_BYTES = 8 * 1024 * 1024
MAX_JSON_BYTES = 2 * 1024 * 1024
ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}
EDITABLE = {"draft", "changes_requested"}


def _staff(user):
    return user.is_authenticated and (user.is_staff or getattr(user, "level", 0) >= 2)


def _mail(customer, subject, body):
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [customer.email])
    except Exception:
        logger.exception("Design notification failed for %s", customer.email)


def _owned(uid, user):
    return get_object_or_404(DesignRequest.objects.select_related("product", "customer"), uid=uid, customer=user)


def _save_preview(obj, data_url, prefix):
    if not data_url:
        return
    try:
        header, encoded = data_url.split(",", 1)
        if header not in ("data:image/png;base64", "data:image/jpeg;base64"):
            return
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > MAX_ASSET_BYTES:
            return
        obj.preview.save(f"{prefix}.png", ContentFile(raw), save=False)
    except (ValueError, binascii.Error):
        return


@login_required
def design_list(request):
    return render(request, "designer/list.html", {"designs": DesignRequest.objects.filter(customer=request.user).select_related("product")})


@login_required
def start_design(request, product_uid):
    product = get_object_or_404(Product, uid=product_uid, customizable=True, is_public=True)
    if not product.mockup_views.exists():
        messages.error(request, "This product is not ready for customization yet.")
        return redirect("details", uid=product.uid)
    design = DesignRequest.objects.create(customer=request.user, product=product)
    return redirect("designer:editor", uid=design.uid)


@login_required
def editor(request, uid):
    design = _owned(uid, request.user)
    if design.status not in EDITABLE:
        return redirect("designer:detail", uid=uid)
    mockups = list(design.product.mockup_views.all())
    return render(request, "designer/editor.html", {"design": design, "mockups": mockups, "sizes": design.product.size.all()})


@login_required
@require_POST
def save_design(request, uid):
    design = _owned(uid, request.user)
    if design.status not in EDITABLE:
        return JsonResponse({"error": "This design is locked."}, status=409)
    if len(request.body) > MAX_JSON_BYTES:
        return JsonResponse({"error": "Design payload is too large."}, status=413)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid design data."}, status=400)
    canvas = data.get("design")
    if not isinstance(canvas, dict) or not isinstance(canvas.get("views", {}), dict):
        return JsonResponse({"error": "Invalid canvas structure."}, status=400)
    valid_view_ids = {str(pk) for pk in design.product.mockup_views.values_list("pk", flat=True)}
    if not set(canvas["views"]).issubset(valid_view_ids):
        return JsonResponse({"error": "Unknown product view."}, status=400)
    quantities = data.get("size_quantities", {})
    valid_sizes = {str(pk) for pk in design.product.size.values_list("pk", flat=True)}
    cleaned = {}
    for key, value in quantities.items():
        if str(key) in valid_sizes:
            try: amount = int(value)
            except (TypeError, ValueError): amount = 0
            if 0 < amount <= 10000: cleaned[str(key)] = amount
    design.current_design = canvas
    design.size_quantities = cleaned
    design.variant = str(data.get("variant", ""))[:100]
    design.note = str(data.get("note", ""))[:4000]
    _save_preview(design, data.get("preview"), f"design-{design.uid}")
    design.save()
    return JsonResponse({"ok": True, "updated": design.updated_at.isoformat()})


@login_required
@require_POST
def upload_asset(request, uid):
    design = _owned(uid, request.user)
    if design.status not in EDITABLE:
        return JsonResponse({"error": "This design is locked."}, status=409)
    upload = request.FILES.get("image")
    if not upload or upload.size > MAX_ASSET_BYTES:
        return JsonResponse({"error": "Choose an image smaller than 8 MB."}, status=400)
    try:
        image = Image.open(upload)
        image.verify()
        if image.format not in ALLOWED_FORMATS or image.width * image.height > 30_000_000:
            raise ValueError
        upload.seek(0)
    except Exception:
        return JsonResponse({"error": "Use a valid PNG, JPEG, or WebP image up to 30 megapixels."}, status=400)
    asset = DesignAsset.objects.create(request=design, image=upload, original_name=Path(upload.name).name[:255])
    return JsonResponse({"id": asset.pk, "url": asset.image.url})


@login_required
@require_POST
def submit_design(request, uid):
    design = _owned(uid, request.user)
    if design.status not in EDITABLE:
        messages.error(request, "This design cannot be submitted in its current state.")
        return redirect("designer:detail", uid=uid)
    if not design.current_design or not design.size_quantities or request.POST.get("rights_confirmed") != "on":
        messages.error(request, "Save artwork, select quantities, and confirm your artwork rights before submitting.")
        return redirect("designer:editor", uid=uid)
    with transaction.atomic():
        number = (design.versions.aggregate(value=Max("number"))["value"] or 0) + 1
        version = DesignVersion(request=design, number=number, design_data=design.current_design)
        if design.preview:
            version.preview.name = design.preview.name
        version.save()
        design.rights_confirmed = True
        design.status = "resubmitted" if design.status == "changes_requested" else "submitted"
        design.save(update_fields=["rights_confirmed", "status", "updated_at"])
    _mail(design.customer, "LOTStore design received", f"We received your {design.product.name} design and will send a quote after review.")
    return redirect("designer:detail", uid=uid)


@login_required
def design_detail(request, uid):
    design = _owned(uid, request.user)
    return render(request, "designer/detail.html", {"design": design})


@login_required
@require_POST
def quote_decision(request, uid, decision):
    design = _owned(uid, request.user)
    quote = get_object_or_404(DesignQuote, request=design)
    if design.status != "quoted" or quote.is_expired or quote.version_id != design.versions.first().id:
        messages.error(request, "This quote is no longer available.")
        return redirect("designer:detail", uid=uid)
    if decision == "decline":
        design.status = "quote_declined"
        design.save(update_fields=["status", "updated_at"])
        return redirect("designer:detail", uid=uid)
    if decision != "accept":
        return HttpResponseForbidden("Invalid decision")
    with transaction.atomic():
        quote = DesignQuote.objects.select_for_update().get(pk=quote.pk)
        if not quote.quote_product:
            product = Product.objects.create(
                user=request.user, name=f"Custom {design.product.name} – {str(design.uid)[:8]}",
                image=design.preview.name or design.product.image.name, price=quote.amount, stock=1,
                description=f"Approved custom design request {design.uid}", pay="Pay before Delivery",
                delivery=design.product.delivery, productType="Single Buy", is_public=False,
            )
            product.categories.set(design.product.categories.all())
            product.size.set(design.product.size.all())
            quote.quote_product = product
            quote.save(update_fields=["quote_product", "updated_at"])
        cart = Cart.objects.filter(user=request.user, cleared=False).order_by("-id").first() or Cart.objects.create(user=request.user)
        item, _ = CartItem.objects.get_or_create(cart=cart, product=quote.quote_product, defaults={"quantity": 1, "info": f"Design request {design.uid}"})
        if item.quantity != 1:
            item.quantity = 1; item.save(update_fields=["quantity"])
        design.status = "quote_accepted"
        design.save(update_fields=["status", "updated_at"])
    return redirect("view_cart")


@login_required
def staff_list(request):
    if not _staff(request.user): return HttpResponseForbidden("Unauthorized")
    return render(request, "designer/staff_list.html", {"designs": DesignRequest.objects.exclude(status="draft").select_related("customer", "product")})


@login_required
def staff_detail(request, uid):
    if not _staff(request.user): return HttpResponseForbidden("Unauthorized")
    design = get_object_or_404(DesignRequest.objects.select_related("customer", "product"), uid=uid)
    return render(request, "designer/staff_detail.html", {"design": design})


@login_required
@require_POST
def staff_action(request, uid):
    if not _staff(request.user): return HttpResponseForbidden("Unauthorized")
    design = get_object_or_404(DesignRequest.objects.select_related("customer", "product"), uid=uid)
    action, body = request.POST.get("action"), request.POST.get("message", "").strip()
    transitions = {
        "submitted": {"changes_requested", "rejected"},
        "resubmitted": {"changes_requested", "rejected"},
        "paid": {"in_production"},
        "in_production": {"sent"},
        "sent": {"delivered"},
    }
    if action == "quote":
        version = design.versions.first()
        try: amount = int(request.POST.get("amount", 0))
        except ValueError: amount = 0
        if not version or amount < 1 or design.status not in {"submitted", "resubmitted"}:
            messages.error(request, "A current submitted version and positive quote amount are required.")
        else:
            DesignQuote.objects.update_or_create(request=design, defaults={"version": version, "amount": amount, "explanation": body})
            design.status = "quoted"; design.save(update_fields=["status", "updated_at"])
            _mail(design.customer, "Your LOTStore design quote is ready", f"Your quote is ₦{amount:,}. Sign in to accept or decline it.")
    elif action in transitions.get(design.status, set()):
        design.status = action; design.save(update_fields=["status", "updated_at"])
        if body: DesignMessage.objects.create(request=design, author=request.user, body=body)
        _mail(design.customer, f"LOTStore design: {design.get_status_display()}", body or f"Your request is now {design.get_status_display()}.")
    else:
        messages.error(request, "That status change is not allowed from the current state.")
    return redirect("designer_staff:detail", uid=uid)


@login_required
def manage_mockups(request, product_uid):
    if not _staff(request.user): return HttpResponseForbidden("Unauthorized")
    product = get_object_or_404(Product, uid=product_uid)
    form = MockupViewForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        mockup = form.save(commit=False); mockup.product = product; mockup.full_clean(); mockup.save()
        product.customizable = True; product.save(update_fields=["customizable"])
        return redirect("designer_staff:mockups", product_uid=product.uid)
    return render(request, "designer/manage_mockups.html", {"product": product, "form": form, "mockups": product.mockup_views.all()})


@login_required
@require_POST
def delete_mockup(request, pk):
    if not _staff(request.user): return HttpResponseForbidden("Unauthorized")
    mockup = get_object_or_404(ProductMockupView, pk=pk); uid = mockup.product.uid; mockup.delete()
    return redirect("designer_staff:mockups", product_uid=uid)
