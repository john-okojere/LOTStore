import json
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from cart.models import CartItem, Payment
from cart.views import _complete_payment
from shelf.models import Category, Product, Sizes
from user.models import User
from .models import DesignQuote, DesignRequest, DesignVersion, ProductMockupView


def image_file(name="test.png"):
    stream = BytesIO()
    Image.new("RGB", (100, 100), "white").save(stream, "PNG")
    return SimpleUploadedFile(name, stream.getvalue(), content_type="image/png")


class DesignerFlowTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(email="buyer@example.com", phone="+2348000000001", password="pass12345")
        self.other = User.objects.create_user(email="other@example.com", phone="+2348000000002", password="pass12345")
        self.staff = User.objects.create_user(email="staff@example.com", phone="+2348000000003", password="pass12345", is_staff=True)
        self.size = Sizes.objects.create(name="Medium")
        self.category = Category.objects.create(name="Shirts")
        self.product = Product.objects.create(user=self.staff, name="Blank Tee", image=image_file(), price=5000, stock=20, description="Tee", customizable=True)
        self.product.size.add(self.size); self.product.categories.add(self.category)
        self.mockup = ProductMockupView.objects.create(product=self.product, name="Front", image=image_file("front.png"))

    def test_customer_can_save_and_submit_immutable_version(self):
        self.client.force_login(self.customer)
        design = DesignRequest.objects.create(customer=self.customer, product=self.product)
        payload = {"design":{"views":{str(self.mockup.pk):[{"type":"text","text":"Faith"}]}}, "size_quantities":{str(self.size.pk):2}}
        response = self.client.post(reverse("designer:save", args=[design.uid]), json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        response = self.client.post(reverse("designer:submit", args=[design.uid]), {"rights_confirmed":"on"})
        self.assertEqual(response.status_code, 302)
        design.refresh_from_db()
        self.assertEqual(design.status, "submitted")
        self.assertEqual(design.versions.count(), 1)
        self.assertEqual(design.versions.first().design_data["views"][str(self.mockup.pk)][0]["text"], "Faith")

    def test_other_customer_cannot_access_design(self):
        design = DesignRequest.objects.create(customer=self.customer, product=self.product)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("designer:detail", args=[design.uid])).status_code, 404)

    def test_quote_acceptance_creates_one_private_cart_item(self):
        design = DesignRequest.objects.create(customer=self.customer, product=self.product, status="quoted", size_quantities={str(self.size.pk):3}, current_design={"views":{}})
        version = DesignVersion.objects.create(request=design, number=1, design_data=design.current_design)
        quote = DesignQuote.objects.create(request=design, version=version, amount=18000)
        self.client.force_login(self.customer)
        url = reverse("designer:quote_decision", args=[design.uid, "accept"])
        self.assertEqual(self.client.post(url).status_code, 302)
        self.client.post(url)
        quote.refresh_from_db(); design.refresh_from_db()
        self.assertFalse(quote.quote_product.is_public)
        self.assertEqual(CartItem.objects.filter(product=quote.quote_product).count(), 1)
        self.assertEqual(design.status, "quote_accepted")

    def test_private_quote_product_is_not_publicly_accessible(self):
        private = Product.objects.create(user=self.customer, name="Private", image=image_file("private.png"), price=1, stock=1, description="Private", is_public=False)
        self.assertEqual(self.client.get(reverse("details", args=[private.uid])).status_code, 404)
        self.assertEqual(self.client.post(reverse("add_to_cart", args=[private.uid]), {}).status_code, 404)

    def test_verified_order_marks_quote_paid(self):
        design = DesignRequest.objects.create(customer=self.customer, product=self.product, status="quote_accepted")
        version = DesignVersion.objects.create(request=design, number=1, design_data={})
        quote_product = Product.objects.create(user=self.customer, name="Quoted", image=image_file("quoted.png"), price=7000, stock=1, description="Quoted", is_public=False)
        DesignQuote.objects.create(request=design, version=version, amount=7000, quote_product=quote_product)
        from cart.models import Cart
        cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(cart=cart, product=quote_product, quantity=1)
        payment = Payment.objects.create(user=self.customer, amount=7000, cart=cart, email=self.customer.email, verified=True)
        _complete_payment(payment)
        design.refresh_from_db()
        self.assertEqual(design.status, "paid")

    def test_customer_and_staff_pages_render(self):
        design = DesignRequest.objects.create(customer=self.customer, product=self.product)
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(reverse("designer:list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("designer:editor", args=[design.uid])).status_code, 200)
        design.status = "submitted"; design.current_design = {"views": {str(self.mockup.pk): []}}; design.size_quantities = {str(self.size.pk): 1}; design.save()
        DesignVersion.objects.create(request=design, number=1, design_data=design.current_design)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("designer_staff:list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("designer_staff:detail", args=[design.uid])).status_code, 200)
