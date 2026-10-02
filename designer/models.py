import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ProductMockupView(models.Model):
    product = models.ForeignKey("shelf.Product", on_delete=models.CASCADE, related_name="mockup_views")
    name = models.CharField(max_length=50)
    image = models.ImageField(upload_to="designer/mockups/%Y/%m/")
    print_x = models.PositiveIntegerField(default=250)
    print_y = models.PositiveIntegerField(default=180)
    print_width = models.PositiveIntegerField(default=400)
    print_height = models.PositiveIntegerField(default=500)
    output_width = models.PositiveIntegerField(default=1800)
    output_height = models.PositiveIntegerField(default=1800)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("position", "id")
        unique_together = (("product", "name"),)

    def clean(self):
        if min(self.print_width, self.print_height, self.output_width, self.output_height) < 1:
            raise ValidationError("Print and output dimensions must be positive.")
        if self.print_x + self.print_width > 900 or self.print_y + self.print_height > 900:
            raise ValidationError("The print area must fit inside the 900 × 900 editor canvas.")

    def __str__(self):
        return f"{self.product} – {self.name}"


class DesignRequest(models.Model):
    STATUSES = [
        ("draft", "Draft"), ("submitted", "Submitted"),
        ("changes_requested", "Changes requested"), ("resubmitted", "Resubmitted"),
        ("quoted", "Quoted"), ("quote_accepted", "Quote accepted"),
        ("quote_declined", "Quote declined"), ("paid", "Paid"),
        ("in_production", "In production"), ("sent", "Sent"),
        ("delivered", "Delivered"), ("rejected", "Rejected"),
    ]
    uid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="design_requests")
    product = models.ForeignKey("shelf.Product", on_delete=models.PROTECT, related_name="design_requests")
    status = models.CharField(max_length=24, choices=STATUSES, default="draft", db_index=True)
    variant = models.CharField(max_length=100, blank=True)
    size_quantities = models.JSONField(default=dict)
    note = models.TextField(blank=True)
    rights_confirmed = models.BooleanField(default=False)
    current_design = models.JSONField(default=dict, blank=True)
    preview = models.ImageField(upload_to="designer/previews/%Y/%m/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)

    @property
    def total_quantity(self):
        total = 0
        for value in self.size_quantities.values():
            try: total += int(value)
            except (TypeError, ValueError): pass
        return total

    def __str__(self):
        return f"{self.product.name} design by {self.customer}"


class DesignVersion(models.Model):
    request = models.ForeignKey(DesignRequest, on_delete=models.CASCADE, related_name="versions")
    number = models.PositiveIntegerField()
    design_data = models.JSONField()
    preview = models.ImageField(upload_to="designer/versions/%Y/%m/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("request", "number"),)
        ordering = ("-number",)


class DesignAsset(models.Model):
    request = models.ForeignKey(DesignRequest, on_delete=models.CASCADE, related_name="assets")
    image = models.ImageField(upload_to="designer/assets/%Y/%m/")
    original_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)


class DesignMessage(models.Model):
    request = models.ForeignKey(DesignRequest, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)


class DesignQuote(models.Model):
    request = models.OneToOneField(DesignRequest, on_delete=models.CASCADE, related_name="quote")
    version = models.ForeignKey(DesignVersion, on_delete=models.PROTECT)
    amount = models.PositiveIntegerField()
    explanation = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    quote_product = models.OneToOneField("shelf.Product", on_delete=models.SET_NULL, null=True, blank=True, related_name="design_quote")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_expired(self):
        from django.utils import timezone
        return bool(self.expires_at and self.expires_at <= timezone.now())
