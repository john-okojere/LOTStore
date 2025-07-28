from django.contrib import admin
from . import models 

admin.site.register(models.Category)
admin.site.register(models.Sizes)
admin.site.register(models.Product)
admin.site.register(models.ProductView)
admin.site.register(models.SearchQuery)