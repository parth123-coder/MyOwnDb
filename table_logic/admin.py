from django.contrib import admin
from .models import UserTable, ActivityLog, APIKey


@admin.register(UserTable)
class UserTableAdmin(admin.ModelAdmin):
    list_display = ['table_name', 'user', 'real_name', 'created_at']
    list_filter = ['created_at']
    search_fields = ['table_name', 'real_name']
    readonly_fields = ['real_name', 'created_at']

    def get_queryset(self, request):
        """Only show user's own tables (unless superuser)"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs  # Superuser sees all
        return qs.filter(user=request.user)  # Others see only their own

    def has_change_permission(self, request, obj=None):
        """Only allow editing own tables"""
        if request.user.is_superuser:
            return True
        if obj is not None and obj.user != request.user:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """Only allow deleting own tables"""
        if request.user.is_superuser:
            return True
        if obj is not None and obj.user != request.user:
            return False
        return super().has_delete_permission(request, obj)

    def has_view_permission(self, request, obj=None):
        """Only allow viewing own tables"""
        if request.user.is_superuser:
            return True
        if obj is not None and obj.user != request.user:
            return False
        return super().has_view_permission(request, obj)

    def save_model(self, request, obj, form, change):
        """Auto-set user when creating via admin"""
        if not change:  # New object
            obj.user = request.user
        super().save_model(request, obj, form, change)


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['action', 'table_name', 'user', 'ip_address', 'created_at']
    list_filter = ['action', 'created_at', 'user']
    search_fields = ['table_name', 'description', 'ip_address']
    readonly_fields = ['user', 'action', 'table_name', 'description', 'metadata', 'ip_address', 'created_at']
    ordering = ['-created_at']
    
    def has_add_permission(self, request):
        """Logs are auto-generated, not manually added"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Logs should not be edited"""
        return False
    
    def get_queryset(self, request):
        """Only show user's own logs (unless superuser)"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'key_prefix', 'is_active', 'last_used_at', 'created_at']
    list_filter = ['is_active', 'created_at', 'user']
    search_fields = ['name', 'key_prefix']
    readonly_fields = ['key_prefix', 'key_hash', 'created_at', 'last_used_at']
    ordering = ['-created_at']
    
    def has_add_permission(self, request):
        """Keys should be created via the dashboard, not admin"""
        return False
    
    def get_queryset(self, request):
        """Only show user's own keys (unless superuser)"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)
