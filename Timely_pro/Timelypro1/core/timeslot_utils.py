from datetime import datetime, timedelta
from core.models import TimeSlot, PracticalPair
from rich.console import Console
from django.utils.timezone import make_aware

console = Console()

def split_time_slot_into_hourly_slots(slot=None):
    """
    Splits a given time slot into hourly slots and stores them in the database.
    If no specific slot is given, processes all time slots that haven't been split yet.
    """
    if slot:
        time_slots = [slot]
    else:
        time_slots = TimeSlot.objects.filter(is_split=False, is_original=True)

    days_processed = set()  # Initialize once outside the loop
    total_created_slots = 0  # Track total created slots

    for ts in time_slots:
        current_time = make_aware(datetime.combine(datetime.today(), ts.start_time))
        end_time = make_aware(datetime.combine(datetime.today(), ts.end_time))

        # Fetch existing splits for the same day to avoid duplicates
        existing_splits = TimeSlot.objects.filter(is_split=True, day=ts.day).values_list('start_time', 'end_time')
        existing_time_ranges = {(split[0], split[1]) for split in existing_splits}

        while current_time < end_time:
            next_hour = current_time + timedelta(hours=1)
            if next_hour > end_time:
                next_hour = end_time  # Handle remaining portion <1 hour

            # Only create slots if they do not already exist
            if (current_time.time(), next_hour.time()) not in existing_time_ranges:
                TimeSlot.objects.create(
                    day=ts.day,
                    start_time=current_time.time(),
                    end_time=next_hour.time(),
                    is_split=True,
                    is_original=False
                )
                total_created_slots += 1  # Increment slot count

            current_time = next_hour

        ts.is_split = True
        ts.save()

        # Ensure generate_practical_pairs is called only once per day
        if ts.day not in days_processed:
            generate_practical_pairs(ts.day)
            days_processed.add(ts.day)  # Mark the day as processed

    if total_created_slots == 0:
        console.print("[bold yellow]No slots were created. Ensure original time slots are long enough.[/bold yellow]")
    else:
        console.print(f"[bold green]Time slots have been split. Total slots created: {total_created_slots}[/bold green]")


def generate_practical_pairs(day=None, max_pairs_per_day=2):
    """
    Generate practical pairs for all split hourly slots.
    If `day` is provided, generate pairs for that day only.
    Allows limiting the number of practical pairs generated per day.
    """
    # Fetch all split slots, optionally filter by day
    if day:
        split_slots = TimeSlot.objects.filter(is_split=True, is_original=False, day=day).order_by('start_time')
    else:
        split_slots = TimeSlot.objects.filter(is_split=True, is_original=False).order_by('day', 'start_time')

    if not split_slots.exists():
        console.print("[bold yellow]No split slots available to generate practical pairs.[/bold yellow]")
        return

    # Group slots by day
    slots_by_day = {}
    for ts in split_slots:
        slots_by_day.setdefault(ts.day, []).append(ts)

    total_pairs_created = 0  # Track total created pairs

    # Generate practical pairs
    for day, slots in slots_by_day.items():
        console.print(f"[bold cyan]Processing practical pairs for day: {day}[/bold cyan]")
        pairs_created_today = 0  # Track pairs created for the current day
        for i in range(len(slots) - 1):
            # Stop creating pairs if the daily limit is reached
            if pairs_created_today >= max_pairs_per_day:
                console.print(
                    f"[bold green]Maximum practical pairs reached for {day} (Limit: {max_pairs_per_day}).[/bold green]"
                )
                break

            current_slot = slots[i]
            next_slot = slots[i + 1]

            # Check if the current slot ends where the next slot begins
            if current_slot.end_time == next_slot.start_time:
                # Avoid duplicate pairs
                if not PracticalPair.objects.filter(first_slot=current_slot, second_slot=next_slot).exists():
                    PracticalPair.objects.create(first_slot=current_slot, second_slot=next_slot)
                    total_pairs_created += 1
                    pairs_created_today += 1

                    console.print(
                        f"[bold green]Created practical pair: {current_slot.start_time}-{current_slot.end_time} and "
                        f"{next_slot.start_time}-{next_slot.end_time}[/bold green]"
                    )

    if total_pairs_created == 0:
        console.print("[bold yellow]No practical pairs were created. Check your time slots for consecutive availability.[/bold yellow]")
    else:
        console.print(f"[bold cyan]Total practical pairs generated: {total_pairs_created}[/bold cyan]")



