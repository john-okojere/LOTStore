# from django.db import models

# class UserActivityLog(models.Model):
#     ACTIVITY_TYPES = [
#         ('login', 'Login'),
#         ('logout', 'Logout'),
#         ('purchase', 'Purchase'),
#         ('view', 'View'),
#         ('update', 'Update'),
#         ('add_to_cart', 'Add to Cart'),
#         ('remove_from_cart', 'Remove from Cart'),
#         ('checkout', 'Checkout'),
#         ('search', 'Search'),
#         # Add more activity types as needed
#     ]

#     user = models.ForeignKey('auth.User', on_delete=models.CASCADE, null=True, blank=True)
#     activity_type = models.CharField(max_length=50, choices=ACTIVITY_TYPES)
#     activity = models.CharField(max_length=255)
#     details = models.TextField(null=True, blank=True)  # Store extra info like item ID, product name, etc.
#     timestamp = models.DateTimeField(auto_now_add=True)
#     request_ip = models.GenericIPAddressField(null=True, blank=True)  # Track the IP address if needed

#     def __str__(self):
#         return f"{self.user.username} - {self.activity_type.capitalize()} {self.activity} at {self.timestamp}"

#     class Meta:
#         ordering = ['-timestamp']  # Show most recent activities first
