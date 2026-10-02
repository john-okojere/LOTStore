from django.contrib import admin
from .models import DesignAsset, DesignMessage, DesignQuote, DesignRequest, DesignVersion, ProductMockupView

admin.site.register([ProductMockupView, DesignRequest, DesignVersion, DesignAsset, DesignMessage, DesignQuote])
