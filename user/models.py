from django.db import models
from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.utils import timezone
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.validators import RegexValidator
from .manager import UserManager
from qrcode import *
import uuid
from django.urls import reverse
import os

GENDER_CATEGORY=(
    ('Male','Male'),
    ('Female','Female'),
)

levels = (
    (1, 1),
    (2, 2),
    (3, 3),
    (4, 4),
    (5, 5),
)

class User(AbstractBaseUser, PermissionsMixin):
    uid = models.UUIDField( default=uuid.uuid4, editable=False)
    first_name = models.CharField(verbose_name='first name', max_length=150, blank=True)
    last_name = models.CharField(verbose_name='last name', max_length=150, blank=True)
    phone_regex = RegexValidator(regex=r'^\+\d{8,15}$|^0\d{10}$', message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.")
    phone = models.CharField(
        validators=[phone_regex],
        max_length=16,
        unique=True,
        help_text="Phone number must be entered in the format: '+999999999'.",
        error_messages={
            'unique': "This Phone has been used already",
        },
        ) # validators should be a list
    email = models.EmailField(verbose_name='email address', unique=True,
        error_messages={
            'unique': "This email has been used already",
        },
    )
    gender = models.CharField(max_length= 20, choices=GENDER_CATEGORY, null=True)
    date_of_birth = models.DateField(null=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    level = models.IntegerField(choices=levels, default=1)
    date_joined = models.DateTimeField(default=timezone.now)
    update_fields = models.DateTimeField(auto_now=True)

    EMAIL_FIELD = 'email'
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['phone']


    objects = UserManager()
    
    def full_name(self):
        return self.first_name + " " + self.last_name

    def qr_code(self):
        qr_code = make(self.uid)
        basename = str(self.uid) + '_QR_CODE.png'
        directory = "media/users/QRCODE/"
        if not os.path.exists(directory):
            os.makedirs(directory)
        qr_code.save('media/users/QRCODE/{}'.format(basename))
        return '/media/users/QRCODE/{}'.format(basename)
    

    def save(self, *args, **kwargs):
        self.qr_code()
        return super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse("profile", kwargs={"uid": self.uid})
    

    def __str__(self):
        return str(self.last_name + " " +self.first_name)

class About(models.Model):
    user = models.OneToOneField(User, on_delete = models.CASCADE, related_name="aboutprofile")
    country = models.CharField(max_length=255)
    state = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    about = models.TextField()
    date_joined = models.DateTimeField(default=timezone.now)
    update_fields = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.user)


class ProfilePic(models.Model):
    user = models.OneToOneField(User, on_delete = models.CASCADE, related_name="profilepic")
    image = models.ImageField(upload_to="profile_pic/%y/%m/%d")
    date_joined = models.DateTimeField(default=timezone.now)
    update_fields = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.user)
        

staff_levels = (
    (1, 1),  # Basic permissions
    (2, 2),  # Intermediate permissions
    (3, 3),  # Advanced permissions
    (4, 4),  # Managerial permissions
    (5, 5),  # Full administrative permissions
)
staff_roles = (
    ('Admin', 'Admin'),
    ('General Manager', 'General Manager'),
    ('Manager', 'Manager'),
    ('Accountant', 'Accountant'),
    ('Sales', 'Sales'),
    ('Logistics', 'Logistics'),
    ('Customer Support', 'Customer Support'),
    ('Marketing', 'Marketing'),
)

class Staff_Application(models.Model):
    uid = models.UUIDField(default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="staff_application")
    role = models.CharField(choices=staff_roles, max_length=25)

class Staff(models.Model):
    uid = models.UUIDField(default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="staff")
    level = models.IntegerField(choices=staff_levels, default=1)
    role = models.CharField(choices=staff_roles, max_length=25)
    country = models.CharField(max_length=255)
    state = models.CharField(max_length=255)
    date_joined = models.DateTimeField(default=timezone.now)
    update_fields = models.DateTimeField(auto_now=True)

    def describe_user(self):
        """Returns a detailed description of the user's role and permissions."""
        role_descriptions = {
            'Admin': {
                1: "Can view basic system settings but cannot make changes.",
                2: "Can manage basic user accounts and system configurations.",
                3: "Can oversee most system operations and handle advanced settings.",
                4: "Can manage all users and perform high-level administrative tasks.",
                5: "Has full control over the system, including access to sensitive settings and data.",
            },
            'Manager': {
                1: "Can view team performance metrics but cannot make changes.",
                2: "Can manage small teams and coordinate daily operations.",
                3: "Can oversee multiple teams and handle operational challenges.",
                4: "Can make strategic decisions and implement business-wide changes.",
                5: "Has full managerial authority, including hiring and firing decisions.",
            },
            'Accountant': {
                1: "Can view financial reports but cannot make edits.",
                2: "Can record transactions and manage simple financial tasks.",
                3: "Can prepare financial statements and reconcile accounts.",
                4: "Can oversee all financial operations and ensure regulatory compliance.",
                5: "Has full access to financial systems and strategic financial decision-making authority.",
            },
            'Sales': {
                1: "Can view product listings but cannot make edits.",
                2: "Can add new products and update existing listings.",
                3: "Can manage promotions and discounts to boost sales.",
                4: "Can analyze sales data and implement strategies for growth.",
                5: "Has full control over sales operations and strategies.",
            },
            'Logistics': {
                1: "Can track orders but cannot manage inventory.",
                2: "Can manage inventory levels and update stock information.",
                3: "Can oversee shipping and returns processes.",
                4: "Can optimize logistics operations and implement new workflows.",
                5: "Has full authority over logistics and supply chain management.",
            },
            'Customer Support': {
                1: "Answer basic customer inquiries.",
                2: "Resolve common issues and escalate complex ones.",
                3: "Handle advanced issues and manage support team.",
                4: "Analyze customer feedback and improve support processes.",
                5: "Full control over customer support operations and policies.",
            },
            'Marketing': {
                1: "Assist in creating marketing materials.",
                2: "Run small campaigns and track basic performance metrics.",
                3: "Develop and execute marketing strategies.",
                4: "Lead marketing initiatives across channels.",
                5: "Full authority over marketing strategies and budgets.",
            },
        }

        role_description = role_descriptions.get(self.role, {}).get(
            self.level,
            "No specific description available for this role and level.",
        )

        return f"{self.user} is a {self.role} at Level {self.level}. {role_description}"

    def __str__(self):
        return f"{self.user} ({self.role}, Level {self.level})"