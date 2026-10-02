from django.core.cache import cache
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from .models import Product

HOMEPAGE_CACHE_KEY = 'homepage_products'


@receiver(post_save, sender=Product)
@receiver(post_delete, sender=Product)
@receiver(m2m_changed, sender=Product.categories.through)
def clear_homepage_cache(**kwargs):
    # New/edited products should show on the homepage immediately.
    cache.delete(HOMEPAGE_CACHE_KEY)
