import base64
import binascii
import json
import logging
import secrets
from pathlib import Path
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Max, Q
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
MAX_ASSETS_PER_DESIGN = 30
GUEST_SESSION_KEY = "designer_guest_key"


def _staff(user):
    return user.is_authenticated and (user.is_staff or getattr(user, "level", 0) >= 2)


def _mail(customer, subject, body):
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [customer.email])
    except Exception:
        logger.exception("Design notification failed for %s", customer.email)


def guest_key(request, create=False):
    """Per-browser key that owns a guest's drafts. It lives in session data,
    so it survives the session-key rotation that happens on login."""
    key = request.session.get(GUEST_SESSION_KEY)
    if not key and create:
        key = secrets.token_urlsafe(24)
        request.session[GUEST_SESSION_KEY] = key
    return key


def claim_guest_designs(request, user):
    key = request.session.get(GUEST_SESSION_KEY)
    if key:
        DesignRequest.objects.filter(customer__isnull=True, guest_key=key).update(customer=user, guest_key="")


def _owner_filter(request):
    key = guest_key(request)
    guest = Q(customer__isnull=True, guest_key=key) if key else Q(pk__in=[])
    if request.user.is_authenticated:
        return Q(customer=request.user) | guest
    return guest


def _owned(request, uid):
    design = get_object_or_404(
        DesignRequest.objects.select_related("product", "customer").filter(_owner_filter(request)), uid=uid
    )
    if request.user.is_authenticated and design.customer_id is None:
        claim_guest_designs(request, request.user)
        design.refresh_from_db()
    return design


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
        ext = "png" if header == "data:image/png;base64" else "jpg"
        obj.preview.save(f"{prefix}.{ext}", ContentFile(raw), save=False)
    except (ValueError, binascii.Error):
        return


def design_list(request):
    if request.user.is_authenticated:
        claim_guest_designs(request, request.user)
    designs = DesignRequest.objects.filter(_owner_filter(request)).select_related("product")
    products = (
        Product.objects.filter(customizable=True, is_public=True, mockup_views__isnull=False)
        .prefetch_related("categories")
        .distinct()
        .order_by("name")
    )
    return render(request, "designer/list.html", {"designs": designs, "customizable_products": products})


def start_design(request, product_uid):
    product = get_object_or_404(Product, uid=product_uid, customizable=True, is_public=True)
    if not product.mockup_views.exists():
        messages.error(request, "This product is not ready for customization yet.")
        return redirect("details", uid=product.uid)
    if request.user.is_authenticated:
        owner = {"customer": request.user}
    else:
        owner = {"customer": None, "guest_key": guest_key(request, create=True)}
    # Re-opening "Customize" continues an untouched draft instead of piling up empty ones.
    blank = next(
        (d for d in DesignRequest.objects.filter(product=product, status="draft", **owner).order_by("-updated_at")[:5]
         if d.object_count == 0),
        None,
    )
    design = blank or DesignRequest.objects.create(product=product, **owner)
    return redirect("designer:editor", uid=design.uid)


def editor(request, uid):
    design = _owned(request, uid)
    if design.status not in EDITABLE:
        return redirect("designer:detail", uid=uid)
    mockups = list(design.product.mockup_views.all())
    assets = design.assets.order_by("-created_at")[:24]
    login_next = f"{reverse('login')}?{urlencode({'next': reverse('designer:editor', args=[design.uid])})}"
    register_next = f"{reverse('register')}?{urlencode({'next': reverse('designer:editor', args=[design.uid])})}"
    return render(request, "designer/editor.html", {
        "design": design, "mockups": mockups, "sizes": design.product.size.all(), "assets": assets,
        "login_next": login_next, "register_next": register_next,
    })


@require_POST
def save_design(request, uid):
    design = _owned(request, uid)
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
    # Products without sizes send a single quantity under the key "0".
    valid_sizes = {str(pk) for pk in design.product.size.values_list("pk", flat=True)} or {"0"}
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


@require_POST
def upload_asset(request, uid):
    design = _owned(request, uid)
    if design.status not in EDITABLE:
        return JsonResponse({"error": "This design is locked."}, status=409)
    if design.assets.count() >= MAX_ASSETS_PER_DESIGN:
        return JsonResponse({"error": f"You can upload up to {MAX_ASSETS_PER_DESIGN} images per design."}, status=400)
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


@require_POST
def submit_design(request, uid):
    design = _owned(request, uid)
    if not request.user.is_authenticated:
        # The quote is emailed and paid from an account; the draft is claimed on sign-in.
        messages.info(request, "Sign in or create a free account to get your quote. Your design is saved and waiting.")
        return redirect(f"{reverse('login')}?{urlencode({'next': reverse('designer:editor', args=[design.uid])})}")
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


TRACK = [
    ("submitted", "Submitted for review"), ("quoted", "Quote ready"), ("quote_accepted", "Quote accepted"),
    ("paid", "Paid"), ("in_production", "In production"), ("sent", "On its way"), ("delivered", "Delivered"),
]
TRACK_POSITION = {"draft": -1, "submitted": 0, "resubmitted": 0, "changes_requested": 0, "quoted": 1,
                  "quote_accepted": 2, "paid": 3, "in_production": 4, "sent": 5, "delivered": 6}


@login_required
def design_detail(request, uid):
    design = _owned(request, uid)
    position = TRACK_POSITION.get(design.status, -1)
    track = [
        {"label": label, "state": "done" if i < position or design.status == "delivered" else "current" if i == position else ""}
        for i, (_, label) in enumerate(TRACK)
    ]
    return render(request, "designer/detail.html", {"design": design, "track": track})


@login_required
@require_POST
def quote_decision(request, uid, decision):
    design = _owned(request, uid)
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
