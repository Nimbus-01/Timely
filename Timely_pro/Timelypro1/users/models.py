#users/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser

class Role(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

class CustomUser(AbstractUser):
    roles = models.ManyToManyField(Role, blank=True)  # Updated to use ManyToManyField for roles

    # Remove role validation from the clean method
    def clean(self):
        pass

    def __str__(self):
        return self.username
