from django.contrib import admin
from django.utils import timezone
from .models import Bill, Brief, Member, Action

admin.site.register(Bill)
admin.site.register(Member)
admin.site.register(Action)

@admin.register(Brief)
class BriefAdmin(admin.ModelAdmin):
    list_display = ["id","bill", "kind", "status", "stage", "created_at", "reviewed_by"]
    list_filter = ["status", "kind", "policy_area"]
    readonly_fields = ["reviewed_by", "reviewed_at", "model_name", "created_at"]
    actions = ["approve", "reject"]

    @admin.action(description="Approve selected briefs")
    def approve(self, request, queryset):
        queryset.update(
            status=Brief.Status.APPROVED,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )

    @admin.action(description="Reject selected briefs")
    def reject(self, request, queryset):
        queryset.update(
            status=Brief.Status.REJECTED,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )