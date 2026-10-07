from django.contrib import admin

from .models import Bill, Member, Action

admin.site.register(Bill)
admin.site.register(Member)
admin.site.register(Action)
