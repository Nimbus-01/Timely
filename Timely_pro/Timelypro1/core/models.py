from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.conf import settings
from datetime import datetime, date, timedelta
from django.contrib.auth import get_user_model

# Degree Model
class Degree(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

# Department Model
class Department(models.Model):
    name = models.CharField(max_length=100)
    degree = models.ForeignKey(Degree, on_delete=models.CASCADE, related_name='departments')
    hod = models.OneToOneField('Faculty', on_delete=models.SET_NULL, null=True, blank=True, related_name='hod_of')

    def clean(self):
        if self.hod:
            if self.hod.department != self:
                raise ValidationError('HOD must be from the same department.')
            if Department.objects.filter(hod=self.hod).exclude(id=self.id).exists():
                raise ValidationError(f'{self.hod} is already HOD of another department.')

    def __str__(self):
        return f"{self.name} ({self.degree.name})"

# Classroom Model
class Classroom(models.Model):
    ROOM_TYPE_CHOICES = [
        ('lecture', 'Lecture Hall'),
        ('lab', 'Lab'),
        ('seminar', 'Seminar Room'),
    ]
    room_number = models.CharField(max_length=10, unique=True)
    capacity = models.PositiveIntegerField()
    room_type = models.CharField(max_length=10, choices=ROOM_TYPE_CHOICES, default='lecture')
    facilities = models.CharField(max_length=255, blank=True)
    room_title = models.CharField(max_length=255, blank=True, null=True)

    def clean(self):
        if self.capacity <= 0:
            raise ValidationError("Capacity must be a positive integer.")
        if not self.room_title:
            self.room_title = f"{self.room_number} ({self.room_type})"

    def __str__(self):
        return self.room_title or f"{self.room_number} ({self.room_type})"

# Subject Model
class Subject(models.Model):
    CLASS_TYPE_CHOICES = [
        ('theory', 'Theory'),
        ('practical', 'Practical'),
        ('seminar', 'Seminar'),
    ]
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    hours_per_week = models.PositiveIntegerField()
    class_type = models.CharField(max_length=10, choices=CLASS_TYPE_CHOICES, default='theory')
    assigned_classroom = models.ForeignKey(
        Classroom,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_subjects'
    )

    def clean(self):
        if self.class_type == 'practical':
            if self.hours_per_week % 2 != 0:
                raise ValidationError('Practical subjects must have an even number of hours per week.')
            if not self.assigned_classroom:
                raise ValidationError('Practical subjects must have an assigned classroom.')

        MAX_HOURS_PER_WEEK = getattr(settings, 'MAX_HOURS_PER_WEEK_PER_SUBJECT', None)
        if MAX_HOURS_PER_WEEK and self.hours_per_week > MAX_HOURS_PER_WEEK:
            raise ValidationError(f'Subject cannot have more than {MAX_HOURS_PER_WEEK} hours per week.')

    def save(self, *args, **kwargs):
        if Subject.objects.filter(code=self.code).exclude(id=self.id).exists():
            raise ValidationError('Subject code must be unique.')
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.code})"

CustomUser = get_user_model()

# Faculty Model
class Faculty(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, limit_choices_to=models.Q(roles__name='Faculty'))
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    degrees = models.ManyToManyField(Degree, related_name='faculties', blank=True)
    subjects = models.ManyToManyField(Subject, related_name='faculties', blank=True)

    def __str__(self):
        return self.user.username

# Student Model
class Student(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, limit_choices_to=models.Q(roles__name='Student'))
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    subjects = models.ManyToManyField(Subject, related_name='students', blank=True)
    year = models.PositiveIntegerField()

    def clean(self):
        for subject in self.subjects.all():
            if subject.department != self.department:
                raise ValidationError(f"Subject {subject.name} is not offered by the student's department.")

    def __str__(self):
        return self.user.username

# TimeSlot Model
class TimeSlot(models.Model):
    DAY_CHOICES = [
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday'),
        ('Sunday', 'Sunday'),
    ]
    day = models.CharField(max_length=10, choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_split = models.BooleanField(default=False)
    is_original = models.BooleanField(default=True)

    @property
    def total_duration(self):
        delta = datetime.combine(date.min, self.end_time) - datetime.combine(date.min, self.start_time)
        return delta.total_seconds() / 3600

    def clean(self):
        if self.start_time >= self.end_time:
            raise ValidationError("Start time must be earlier than end time.")

    def __str__(self):
        return f"{self.day}: {self.start_time} - {self.end_time}"

# PracticalPair Model
class PracticalPair(models.Model):
    first_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, related_name='first_pair')
    second_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, related_name='second_pair')

    def __str__(self):
        return f"{self.first_slot.day}: {self.first_slot.start_time} - {self.second_slot.end_time}"

# Timetable Model
class Timetable(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, null=True, blank=True, related_name='timetables')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE,blank=True,null=True)
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE)

    def clean(self):
        if self.time_slot.is_original:
            raise ValidationError("Cannot use original time slots in a timetable. Use split slots only.")

        conflicting_faculty = Timetable.objects.filter(faculty=self.faculty, time_slot=self.time_slot).exclude(id=self.id)
        if conflicting_faculty.exists():
            raise ValidationError(f'Faculty {self.faculty} is already assigned during this time.')

        conflicting_classroom = Timetable.objects.filter(classroom=self.classroom, time_slot=self.time_slot).exclude(id=self.id)
        if conflicting_classroom.exists():
            raise ValidationError(f'Classroom {self.classroom} is already booked during this time.')

        if self.subject:
            enrolled_students = self.subject.students.count()
            if self.classroom.capacity < enrolled_students:
                raise ValidationError(f'Classroom capacity is insufficient for the assigned subject.')

    def __str__(self):
        return f"{self.department} - {self.subject} ({self.time_slot.start_time} - {self.time_slot.end_time})"

# Notification Model
class Notification(models.Model):
    CustomUser = get_user_model()
    TYPE_CHOICES = [
        ('info', 'Information'),
        ('alert', 'Alert'),
        ('timetable_update', 'Timetable Update'),
    ]
    message = models.CharField(max_length=255)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='info')
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username}: {self.message}"

# AuditLog Model
class AuditLog(models.Model):
    CustomUser = get_user_model()
    action = models.CharField(max_length=50)
    timestamp = models.DateTimeField(auto_now_add=True)
    performed_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    details = models.TextField()

    def __str__(self):
        return f"{self.action} by {self.performed_by.username} at {self.timestamp}"
