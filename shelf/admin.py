from django.contrib import admin
from import_export.admin import ImportExportModelAdmin

from . import models


@admin.register(models.Category)
class CategoryAdmin(ImportExportModelAdmin):
    list_display = ("name", "created_date")
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(models.Sizes)
class SizesAdmin(ImportExportModelAdmin):
    list_display = ("name", "created_date")
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(models.Product)
class ProductAdmin(ImportExportModelAdmin):
    list_display = ("name", "price", "stock", "pay", "delivery", "productType", "created_date")
    list_filter = ("pay", "delivery", "productType", "created_date")
    search_fields = ("name", "description")
    ordering = ("-created_date",)


@admin.register(models.ProductView)
class ProductViewAdmin(ImportExportModelAdmin):
    list_display = ("product", "user", "ip_address", "state", "country", "duration", "timestamp")
    list_filter = ("state", "country", "timestamp")
    search_fields = ("product__name", "user__email", "ip_address")
    ordering = ("-timestamp",)


@admin.register(models.SearchQuery)
class SearchQueryAdmin(ImportExportModelAdmin):
    list_display = ("query", "user", "ip_address", "state", "country", "timestamp")
    list_filter = ("state", "country", "timestamp")
    search_fields = ("query", "user__email", "ip_address")
    ordering = ("-timestamp",)
