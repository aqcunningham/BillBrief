import copy
from django.contrib import admin
from django.utils import timezone

from .models import Bill, Brief


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ["__str__", "title", "latest_action_date"]
    search_fields = ["title", "bill_type", "number"]

@admin.register(Brief)
class BriefAdmin(admin.ModelAdmin):
    list_display = ["id", "bill", "status", "stage", "as_of", "reused_from", "created_at", "reviewed_by"]
    list_filter = ["status", "policy_area"]
    autocomplete_fields = ["bill"]
    readonly_fields = ["origin_note", "stage", "status_text", "next_step", "review_record",
                       "model_name", "created_at", "as_of", "crs_version", "reused_from"]
    actions = ["approve", "reject"]

    fieldsets = [
        ("Bill", {"fields": ["bill"]}),
        ("Explanation — check against the CRS summary", {
            "fields": ["origin_note", "summary", "why_it_matters", "who_is_affected", "policy_area"],
        }),
        ("Facts — written by code, shown to readers as is", {
            "fields": ["stage", "status_text", "next_step"],
        }),
        ("Decision", {"fields": ["status", "review_record"]}),
        ("Where this came from", {
            "fields": ["as_of", "crs_version", "reused_from", "model_name", "created_at"],
            "classes": ["collapse"],
        }),
    ]

    def get_fieldsets(self, request, obj=None):
        """Hide 'What's next' when there isn't one."""
        fieldsets = copy.deepcopy(self.fieldsets)
        if obj and not obj.whats_next:
            for _, options in fieldsets:
                if "next_step" in options["fields"]:
                    options["fields"].remove("next_step")
        return fieldsets

    @admin.display(description="Source")
    def origin_note(self, obj):
        if obj.reused_from:
            return (f"Copied from approved brief {obj.reused_from.id} (the CRS summary hasn't changed). "
                    "Already approved once; check that it still fits the facts below.")
        return "Written fresh by Claude. Check every line against the CRS summary."

    @admin.display(description="What's next")
    def next_step(self, obj):
        return obj.whats_next

    @admin.display(description="Reviewed")
    def review_record(self, obj):
        if obj.reviewed_by:
            when = timezone.localtime(obj.reviewed_at).strftime("%b %-d, %Y at %-I:%M %p")
            return f"{obj.get_status_display()} by {obj.reviewed_by} on {when}"
        return "Not yet"

    def save_model(self, request, obj, form, change):
        """Record the reviewer whenever status changes to approved or rejected, even via the form."""
        if "status" in form.changed_data and obj.status != Brief.Status.DRAFT:
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)

    @admin.action(description="Approve selected briefs")
    def approve(self, request, queryset):
        queryset.update(status=Brief.Status.APPROVED, reviewed_by=request.user, reviewed_at=timezone.now())

    @admin.action(description="Reject selected briefs")
    def reject(self, request, queryset):
        queryset.update(status=Brief.Status.REJECTED, reviewed_by=request.user, reviewed_at=timezone.now())