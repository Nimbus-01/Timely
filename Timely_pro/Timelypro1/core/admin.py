# core/admin.py

from django.contrib import admin
from .models import (
    Degree, Department, Subject, Faculty, Classroom,
    TimeSlot, Timetable, Notification, Student, AuditLog
)
from core.timeslot_utils import split_time_slot_into_hourly_slots, generate_practical_pairs

# Register models to appear in the Django admin site

@admin.register(Degree)
class DegreeAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'degree', 'hod')
    search_fields = ('name', 'degree__name', 'hod__user__username')
    list_filter = ('degree',)

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'department', 'hours_per_week', 'class_type', 'assigned_classroom')
    search_fields = ('name', 'code', 'department__name')
    list_filter = ('department', 'class_type')

@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ('user', 'department')
    search_fields = ('user__username', 'user__email', 'department__name')
    list_filter = ('department',)

@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = ('room_title','room_number', 'capacity', 'room_type')
    search_fields = ('room_number',)
    list_filter = ('room_type',)

# core/admin.py
@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ('day', 'start_time', 'end_time', 'is_split', 'is_original')
    list_filter = ('day',)

    def get_queryset(self, request):
        # Show only original slots in the admin panel
        qs = super().get_queryset(request)
        return qs

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.is_original and not obj.is_split:
            try:
                split_time_slot_into_hourly_slots(obj)  # Splitting now handles pairing internally
                self.message_user(request, "Time slot split and practical pairs generated successfully.", level='success')
            except Exception as e:
                self.message_user(request, f"Error processing time slot: {e}", level='error')


@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
    list_display = ('department', 'faculty', 'subject', 'classroom', 'get_day', 'get_start_time', 'get_end_time')
    search_fields = ('department__name', 'faculty__user__username', 'subject__name')
    list_filter = ('department', 'time_slot__day')

    def get_day(self, obj):
        return obj.time_slot.day
    get_day.short_description = 'Day'

    def get_start_time(self, obj):
        return obj.time_slot.start_time
    get_start_time.short_description = 'Start Time'

    def get_end_time(self, obj):
        return obj.time_slot.end_time
    get_end_time.short_description = 'End Time'

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'notification_type', 'timestamp', 'is_read')
    list_filter = ('notification_type', 'is_read', 'timestamp')
    search_fields = ('user__username', 'message')

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('user', 'department', 'year')
    search_fields = ('user__username', 'user__email', 'department__name')
    list_filter = ('department', 'year')

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'performed_by', 'timestamp')
    search_fields = ('performed_by__username', 'action')
    list_filter = ('timestamp',)
    readonly_fields = ('action', 'performed_by', 'timestamp', 'details')
