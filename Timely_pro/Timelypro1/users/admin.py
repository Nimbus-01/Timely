from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser, Role

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    # Adding custom fields to the admin panel
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('roles',)}),  # Adding 'roles' to the admin form for editing users
    )
    # Remove 'roles' from the add_fieldsets to avoid adding it before the instance is saved
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'first_name', 'last_name')
        }),
    )

    list_display = ('username', 'first_name', 'last_name', 'is_staff')
    search_fields = ('username', 'first_name', 'last_name')
    list_filter = UserAdmin.list_filter + ('roles__name',)

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

# Signal to assign roles after user has been created
@receiver(post_save, sender=CustomUser)
def assign_roles(sender, instance, created, **kwargs):
    if created and hasattr(instance, '_roles'):
        instance.roles.set(instance._roles)
