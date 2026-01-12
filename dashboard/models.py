from django.db import models
from django.utils import timezone

# Create your models here.
class User(models.Model):
    name = models.CharField(max_length=50, blank=False, null=False)
    email = models.EmailField(blank=False, null=False)
    password = models.CharField(max_length=50, blank=False, null=False)
    Date_time = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name