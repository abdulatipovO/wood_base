from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import *

# Register your models here.

class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'first_name', 'last_name', 'email', 'is_staff', 'is_active']
    # fieldsets = UserAdmin.fieldsets + (
    #     (None, {'fields': ('is_staff', 'is_active')}),
    # )

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Container)
admin.site.register(ProductSize)
admin.site.register(Product)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(ExpenseType)
admin.site.register(Worker)
admin.site.register(Expense)
admin.site.register(Client)
admin.site.register(ClientAccount)
admin.site.register(Payment)
admin.site.register(Note)
admin.site.register(Supplier)
admin.site.register(PaymentToSupplier)



