from rest_framework import serializers
from .models import (
    Degree, Department, Subject, Faculty, Classroom,
    TimeSlot, Timetable, Notification, Student
)
from users.models import CustomUser, Role
from django.contrib.auth import get_user_model

CustomUser = get_user_model()

# Role Serializer
class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'name']

# Custom User Serializer
class CustomUserSerializer(serializers.ModelSerializer):
    roles = RoleSerializer(many=True, read_only=True)

    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'roles']

# Degree Serializer
class DegreeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Degree
        fields = '__all__'

# Department Serializer
class DepartmentSerializer(serializers.ModelSerializer):
    degree = DegreeSerializer()

    class Meta:
        model = Department
        fields = '__all__'

# Flat Subject Serializer
class FlatSubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name']

# Subject Serializer
class SubjectSerializer(serializers.ModelSerializer):
    department = DepartmentSerializer()

    class Meta:
        model = Subject
        fields = '__all__'

# Faculty Serializer
class FacultySerializer(serializers.ModelSerializer):
    user = CustomUserSerializer()
    department = DepartmentSerializer()
    subjects = FlatSubjectSerializer(many=True)

    class Meta:
        model = Faculty
        fields = '__all__'

# Classroom Serializer
class ClassroomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Classroom
        fields = '__all__'

# Time Slot Serializer
class TimeSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeSlot
        fields = ['id', 'day', 'start_time', 'end_time', 'total_duration']
        read_only_fields = ['total_duration']

# Timetable Serializer
class TimetableSerializer(serializers.ModelSerializer):
    department = DepartmentSerializer()
    faculty = FacultySerializer()
    subject = SubjectSerializer()
    classroom = ClassroomSerializer()
    time_slot = TimeSlotSerializer()

    class Meta:
        model = Timetable
        fields = '__all__'

# Notification Serializer
class NotificationSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer()

    class Meta:
        model = Notification
        fields = '__all__'

# Student Serializer
class StudentSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer()
    department = DepartmentSerializer()
    subjects = FlatSubjectSerializer(many=True)

    class Meta:
        model = Student
        fields = '__all__'
