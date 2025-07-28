from django.contrib import admin
from .models import  User, ProfilePic, About, Staff
from import_export.admin import ImportExportMixin



class UserAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = ('first_name','last_name','phone','email','gender','is_staff','is_active','date_joined','update_fields',)
    list_filter = ('first_name','last_name','phone','email','gender','is_staff','is_active','date_joined','update_fields',)
    search_fields = ('first_name','last_name','phone','email','gender','is_staff','is_active','date_joined','update_fields',)
    ordering = ('email',)
    filter_horizontal = ('groups', 'user_permissions',)
admin.site.register(User, UserAdmin)


class AboutAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = ('user', 'country','state','address')
    list_filter = ('country','state','address',)
    search_fields = ('user', 'country','state','address')
    ordering = ('user',)
admin.site.register(About, AboutAdmin)



class ProfileAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = ('user', 'image')
    list_filter = ('user', 'image')
    search_fields = ('user', 'image')
    ordering = ('user',)
admin.site.register(ProfilePic, ProfileAdmin)


admin.site.register(Staff)