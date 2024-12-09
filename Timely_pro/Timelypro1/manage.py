#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schedulify.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
'''from collections import defaultdict
from django.conf import settings
from core.models import Timetable, TimeSlot, Faculty, Subject, Classroom, Department
from django.db import transaction
from datetime import time, datetime, timedelta
import random
from rich.console import Console
from rich import box
from rich.table import Table

console = Console()

def generate_timetable():
    try:
        console.print("[bold blue]Starting timetable generation...[/bold blue]")

        # Start a transaction for safety
        with transaction.atomic():
            # Clear existing timetable entries
            Timetable.objects.all().delete()
            console.print("[bold red]Cleared existing timetable entries.[/bold red]")

            # Split time slots into hourly slots if not already done
            if not TimeSlot.objects.filter(total_duration=1).exists():
                split_time_slot_into_hourly_slots()

            # Fetch all necessary data
            time_slots = list(TimeSlot.objects.all())
            faculties = Faculty.objects.all()
            classrooms = Classroom.objects.all()
            departments = Department.objects.all()

            # Initialize availability tracking
            faculty_availability = {faculty.id: set(ts.id for ts in time_slots) for faculty in faculties}
            classroom_availability = {classroom.id: set(ts.id for ts in time_slots) for classroom in classrooms}

            # Helper functions
            def get_session_duration(subject):
                if subject.class_type == 'theory':
                    return settings.CLASS_DURATION_THEORY  # Duration from settings
                elif subject.class_type == 'practical':
                    return settings.CLASS_DURATION_PRACTICAL  # Duration from settings
                return 1

            def get_suitable_classrooms(subject):
                if subject.class_type == 'practical' and subject.assigned_classroom:
                    return [subject.assigned_classroom]  # Use assigned classroom if specified
                elif subject.class_type == 'practical':
                    return classrooms.filter(room_type='lab')
                else:
                    return classrooms.filter(room_type='lecture')

            # Create a table to display the allocation details
            table = Table(title="Timetable Generation Summary", box=box.SIMPLE_HEAVY)
            table.add_column("Department", style="cyan", no_wrap=True)
            table.add_column("Subject", style="magenta")
            table.add_column("Faculty", style="green")
            table.add_column("Classroom", style="yellow")
            table.add_column("Time Slot", style="blue")

            # Shuffle data to randomize allocation
            random.shuffle(time_slots)
            faculties = list(faculties)
            random.shuffle(faculties)
            classrooms = list(classrooms)
            random.shuffle(classrooms)

            # Loop through each department and allocate subjects evenly throughout the week
            for department in departments:
                subjects = Subject.objects.filter(department=department)

                for subject in subjects:
                    # Determine session duration and number of sessions required per week
                    session_duration = get_session_duration(subject)
                    number_of_sessions = subject.hours_per_week // session_duration

                    # Allocate sessions across available days and time slots
                    sessions_allocated = 0

                    for idx, time_slot in enumerate(time_slots):
                        if sessions_allocated >= number_of_sessions:
                            break

                        # Check if the current time slot matches the required duration
                        if session_duration == 2:
                            # For practicals, we need two consecutive 1-hour slots
                            if idx + 1 >= len(time_slots):
                                continue  # Not enough slots left for a 2-hour session
                            next_time_slot = time_slots[idx + 1]
                            if time_slot.day != next_time_slot.day or time_slot.total_duration != 1 or next_time_slot.total_duration != 1:
                                continue  # Slots must be consecutive and of 1-hour duration

                        # Check faculty availability
                        faculties_who_can_teach = subject.faculties.all()
                        available_faculty = [
                            faculty for faculty in faculties_who_can_teach
                            if time_slot.id in faculty_availability[faculty.id]
                        ]
                        if not available_faculty:
                            continue

                        # Shuffle available faculty to randomize the selection
                        random.shuffle(available_faculty)

                        # Check classroom availability
                        suitable_classrooms = get_suitable_classrooms(subject)
                        available_classroom = [
                            classroom for classroom in suitable_classrooms
                            if time_slot.id in classroom_availability[classroom.id]
                        ]
                        if not available_classroom:
                            continue

                        # Shuffle available classrooms to randomize the selection
                        random.shuffle(available_classroom)

                        # Allocate the first available faculty and classroom
                        faculty = available_faculty[0]
                        classroom = available_classroom[0]

                        # Schedule the session
                        Timetable.objects.create(
                            department=department,
                            faculty=faculty,
                            subject=subject,
                            classroom=classroom,
                            time_slot=time_slot
                        )

                        # Update availability
                        faculty_availability[faculty.id].remove(time_slot.id)
                        classroom_availability[classroom.id].remove(time_slot.id)

                        # If practical, also allocate the next consecutive slot
                        if session_duration == 2:
                            Timetable.objects.create(
                                department=department,
                                faculty=faculty,
                                subject=subject,
                                classroom=classroom,
                                time_slot=next_time_slot
                            )
                            faculty_availability[faculty.id].remove(next_time_slot.id)
                            classroom_availability[classroom.id].remove(next_time_slot.id)

                        # Add details to the console table
                        table.add_row(
                            department.name,
                            subject.name,
                            faculty.user.username,
                            classroom.room_number,
                            f"{time_slot.day} {time_slot.start_time} - {time_slot.end_time}"
                        )

                        sessions_allocated += 1

                    # If unable to schedule all sessions, log the subject
                    if sessions_allocated < number_of_sessions:
                        console.print(f"[bold red]Could not schedule all sessions for subject {subject.name}. Remaining: {number_of_sessions - sessions_allocated}[/bold red]")

            console.print(table)
            console.print("\n[bold blue]Timetable generation completed successfully.[/bold blue]")

        return {"status": "success", "message": "Timetable generated successfully."}
    except Exception as e:
        console.print(f"[bold red]An error occurred: {str(e)}[/bold red]")
        return {"status": "error", "message": str(e)}

def split_time_slot_into_hourly_slots(slot=None):
    """
    This function splits a given time slot into hourly slots and stores them in the database.
    If no specific slot is given, it processes all time slots.
    """
    if slot:
        time_slots = [slot]
    else:
        time_slots = TimeSlot.objects.all()

    for ts in time_slots:
        current_time = datetime.combine(datetime.today(), ts.start_time)
        end_time = datetime.combine(datetime.today(), ts.end_time)

        while current_time < end_time:
            next_hour = current_time + timedelta(hours=1)

            # Ensure that we do not go beyond the end_time
            if next_hour > end_time:
                break

            # Create the hourly time slot
            TimeSlot.objects.create(
                day=ts.day,
                start_time=current_time.time(),
                end_time=next_hour.time()
            )

            current_time = next_hour

    console.print("[bold green]Time slots have been split into hourly slots.[/bold green]")

# Example usage:
split_time_slot_into_hourly_slots()
'''