from django.db import models
from django.contrib.auth.models import User  # ← User comes from here!
from django.utils import timezone


class UserTable(models.Model):  # Fixed: models.Model (capital M)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    table_name = models.CharField(max_length=50)      # Display name (what user sees)
    real_name = models.CharField(max_length=100)      # Actual SQLite table name (u1_products)
    schema = models.JSONField()                       # Stores columns as JSON
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        # Ensure same user can't have duplicate table names
        unique_together = ['user', 'table_name']

    def __str__(self):
        return f"{self.user.username}'s {self.table_name}"

class ActivityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=50)        # CREATE_TABLE, INSERT_ROW, DELETE_ROW, etc.
    table_name = models.CharField(max_length=100)   # Which table was affected
    description = models.TextField()                # Human-readable description
    metadata = models.JSONField(null=True)          # Extra data (row_id, old/new values)
    ip_address = models.GenericIPAddressField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.action} on {self.table_name} by {self.user.username}"


class APIKey(models.Model):
    """
    API Key for secure external access to user's data.
    The actual key is only shown ONCE when created - we store the hash.
    """
    import secrets
    import hashlib
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_keys')
    name = models.CharField(max_length=100)              # e.g., "My Python App", "Production"
    key_prefix = models.CharField(max_length=8)          # First 8 chars of key (for identification)
    key_hash = models.CharField(max_length=64, unique=True)  # SHA-256 hash of the full key
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'API Key'
        verbose_name_plural = 'API Keys'
    
    def __str__(self):
        return f"{self.name} ({self.key_prefix}...)"
    
    @classmethod
    def generate_key(cls):
        """Generate a new random API key with sk_ prefix"""
        import secrets
        # 32 bytes = 64 hex chars, plus prefix = 67 chars total
        raw_key = f"sk_{secrets.token_hex(32)}"
        return raw_key
    
    @classmethod
    def hash_key(cls, raw_key):
        """Hash a raw key using SHA-256"""
        import hashlib
        return hashlib.sha256(raw_key.encode()).hexdigest()
    
    @classmethod
    def create_key(cls, user, name):
        """
        Create a new API key for a user.
        Returns (APIKey instance, raw_key) - raw_key is only available here!
        """
        raw_key = cls.generate_key()
        key_hash = cls.hash_key(raw_key)
        key_prefix = raw_key[:10]  # "sk_" + first 7 chars
        
        api_key = cls.objects.create(
            user=user,
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
        )
        return api_key, raw_key
    
    @classmethod
    def authenticate(cls, raw_key):
        """
        Authenticate a raw API key.
        Returns the APIKey object if valid, None otherwise.
        """
        if not raw_key or not raw_key.startswith('sk_'):
            return None
        
        key_hash = cls.hash_key(raw_key)
        try:
            api_key = cls.objects.select_related('user').get(
                key_hash=key_hash,
                is_active=True
            )
            # Update last used timestamp
            api_key.last_used_at = timezone.now()
            api_key.save(update_fields=['last_used_at'])
            return api_key
        except cls.DoesNotExist:
            return None        