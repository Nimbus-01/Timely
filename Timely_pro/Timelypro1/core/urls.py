# core/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import (
    DegreeViewSet, DepartmentViewSet, SubjectViewSet, FacultyViewSet,
    ClassroomViewSet, TimeSlotViewSet, TimetableViewSet, NotificationViewSet,
    StudentViewSet, HomeView
)

router = DefaultRouter()
router.register(r'degrees', DegreeViewSet)
router.register(r'departments', DepartmentViewSet)
router.register(r'subjects', SubjectViewSet)
router.register(r'faculties', FacultyViewSet)
router.register(r'classrooms', ClassroomViewSet)
router.register(r'time-slots', TimeSlotViewSet)
router.register(r'timetables', TimetableViewSet)
router.register(r'notifications', NotificationViewSet)
router.register(r'students', StudentViewSet)

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('', include(router.urls)),
]
