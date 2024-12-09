import logging
import random
from collections import defaultdict
from functools import partial

from django.db import transaction
from deap import base, creator, tools
from core.models import Timetable, TimeSlot, Subject, PracticalPair

# Logging setup
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

# Initialize DEAP Tools
creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
creator.create("Individual", list, fitness=creator.FitnessMin)
toolbox = base.Toolbox()

# Constants
POPULATION_SIZE = 100
MUTATION_RATE = 0.3
CROSSOVER_RATE = 0.9
GENERATIONS = 300

# Single classroom for all sessions
single_classroom = "Room 101"

# Utility function for session validation
def is_valid_session(session):
    logger.debug(f"Validating session: {session}")
    if not session:
        logger.warning(f"Invalid session encountered: {session}")
        return False
    if isinstance(session, dict) and session.get("subject") and session.get("time_slot"):
        return True
    logger.warning(f"Invalid session encountered: {session}")
    return False

def get_sorted_practical_pairs():
    logger.info("Fetching practical pairs...")
    try:
        practical_pairs = list(PracticalPair.objects.select_related('first_slot', 'second_slot').all())
        if not practical_pairs:
            logger.warning("No practical pairs found.")
        return practical_pairs
    except Exception as e:
        logger.error(f"Error fetching practical pairs: {e}")
        return []

def get_sorted_time_slots():
    logger.info("Fetching sorted time slots...")
    try:
        paired_slots = PracticalPair.objects.values_list('first_slot', 'second_slot', flat=False)
        paired_slot_ids = {slot_id for pair in paired_slots for slot_id in pair}

        remaining_time_slots = TimeSlot.objects.filter(
            is_split=True,
            is_original=False
        ).exclude(id__in=paired_slot_ids).order_by('day', 'start_time')

        if not remaining_time_slots.exists():
            logger.warning("No available time slots for theory allocation.")
        return list(remaining_time_slots)
    except Exception as e:
        logger.error(f"Error fetching time slots: {e}")
        return []

def initialize_session(practical_pairs, all_subjects, remaining_time_slots):
    logger.info(f"Initializing session with practical pairs: {practical_pairs}, subjects: {all_subjects}, and time slots: {remaining_time_slots}")

    # Filter valid subjects
    valid_subjects = [s for s in all_subjects if s is not None and hasattr(s, "class_type")]
    if not valid_subjects:
        logger.error("No valid subjects available for session initialization.")
        return {"subject": None, "time_slot": None}

    practical_subjects = [s for s in valid_subjects if s.class_type.lower() == "practical"]
    theory_subjects = [s for s in valid_subjects if s.class_type.lower() == "theory"]

    if practical_pairs and practical_subjects:
        valid_pairs = [pair for pair in practical_pairs if pair is not None]
        if valid_pairs:
            practical_pair = random.choice(valid_pairs)
            subject = random.choice(practical_subjects)
            if subject:
                practical_pairs.remove(practical_pair)  # Remove assigned pair
                logger.info(f"Assigned Practical Subject: {subject} to Time Slot Pair: {practical_pair}")
                return {"subject": subject, "time_slot": (practical_pair.first_slot, practical_pair.second_slot)}

    if remaining_time_slots and theory_subjects:
        time_slot = random.choice(remaining_time_slots)
        subject = random.choice(theory_subjects)
        if subject:
            remaining_time_slots.remove(time_slot)  # Remove assigned slot
            logger.info(f"Assigned Theory Subject: {subject} to Time Slot: {time_slot}")
            return {"subject": subject, "time_slot": time_slot}

    logger.warning("Failed to initialize a valid session.")
    return {"subject": None, "time_slot": None}

def fitness_function(individual):
    logger.debug("Evaluating fitness for individual...")
    conflicts = 0
    time_slot_usage = set()

    for session in individual:
        if not is_valid_session(session):
            conflicts += 10
            logger.debug(f"Conflict detected for invalid session: {session}")
            continue

        subject = session["subject"]
        if subject is None or not hasattr(subject, "class_type"):
            conflicts += 10
            logger.debug(f"Conflict detected for invalid subject: {subject}")
            continue

        time_slot = session["time_slot"]
        if isinstance(time_slot, tuple):
            for slot in time_slot:
                if slot in time_slot_usage:
                    conflicts += 5
                else:
                    time_slot_usage.add(slot)
        else:
            if time_slot in time_slot_usage:
                conflicts += 5
            else:
                time_slot_usage.add(time_slot)

        subject_hours = sum(1 for s in individual if is_valid_session(s) and s["subject"] == subject)
        if subject.class_type == "theory" and subject_hours > 3:
            conflicts += 5

    logger.debug(f"Fitness conflicts: {conflicts}")
    return (conflicts,)

def crossover(ind1, ind2):
    logger.debug("Performing crossover...")
    if random.random() < CROSSOVER_RATE:
        if len(ind1) < 2 or len(ind2) < 2:
            logger.warning("Skipping crossover: Individuals too small.")
            return
        point1 = random.randint(1, len(ind1) - 2)
        point2 = random.randint(point1, len(ind1) - 1)
        ind1[point1:point2], ind2[point1:point2] = ind2[point1:point2], ind1[point1:point2]

def mutate(individual, practical_pairs, remaining_time_slots, subjects):
    logger.debug("Applying mutation...")
    
    if not individual:
        logger.warning("Skipping mutation: Individual is empty.")
        return individual

    if random.random() < MUTATION_RATE:
        slot_idx = random.randint(0, len(individual) - 1)
        session = individual[slot_idx]

        if not is_valid_session(session):
            logger.warning(f"Skipping invalid session during mutation: {session}")
            return individual

        valid_subjects = [s for s in subjects if s is not None and hasattr(s, "class_type")]
        if not valid_subjects:
            logger.warning("No valid subjects available for mutation.")
            return individual

        # Assign a new random subject
        session["subject"] = random.choice(valid_subjects)

        # Handle mutation for practical subjects
        if session["subject"].class_type == "practical" and practical_pairs:
            valid_pairs = [pair for pair in practical_pairs if pair is not None]
            if valid_pairs:
                practical_pair = random.choice(valid_pairs)
                session["time_slot"] = (practical_pair.first_slot, practical_pair.second_slot)

                # Safely remove the practical pair after assignment
                try:
                    practical_pairs.remove(practical_pair)
                    logger.info(f"Practical pair {practical_pair} removed from pool during mutation.")
                except ValueError:
                    logger.warning(f"Practical pair {practical_pair} was not found in the pool during mutation.")

            else:
                logger.warning("No practical pairs available for mutation.")

        # Handle mutation for theory subjects
        elif remaining_time_slots:
            valid_slots = [slot for slot in remaining_time_slots if slot is not None]
            if valid_slots:
                time_slot = random.choice(valid_slots)
                session["time_slot"] = time_slot

                # Safely remove the time slot after assignment
                try:
                    remaining_time_slots.remove(time_slot)
                    logger.info(f"Time slot {time_slot} removed from pool during mutation.")
                except ValueError:
                    logger.warning(f"Time slot {time_slot} was not found in the pool during mutation.")
            else:
                logger.warning("No remaining time slots available for mutation.")

    return individual


def generate_timetable():
    logger.info("Starting timetable generation...")
    try:
        with transaction.atomic():
            Timetable.objects.all().delete()
        logger.info("Cleared existing timetable entries.")

        subjects = [s for s in Subject.objects.all() if s and hasattr(s, "class_type")]
        practical_pairs = get_sorted_practical_pairs()
        remaining_time_slots = get_sorted_time_slots()

        if not subjects:
            logger.error("No valid subjects available.")
            return {"status": "error", "message": "No valid subjects available."}
        if not practical_pairs:
            logger.error("No practical pairs available.")
            return {"status": "error", "message": "No practical pairs available."}
        if not remaining_time_slots:
            logger.error("No time slots available.")
            return {"status": "error", "message": "No time slots available."}

        toolbox.register(
            "attr_slot", partial(initialize_session, practical_pairs, subjects, remaining_time_slots)
        )
        toolbox.register("individual", tools.initRepeat, creator.Individual, toolbox.attr_slot, n=40)
        toolbox.register("population", tools.initRepeat, list, toolbox.individual)
        toolbox.register("evaluate", fitness_function)
        toolbox.register("mate", crossover)
        toolbox.register("mutate", partial(mutate, practical_pairs, remaining_time_slots, subjects))
        toolbox.register("select", tools.selTournament, tournsize=3)

        population = toolbox.population(n=POPULATION_SIZE)
        if not population:
            logger.error("Population initialization failed.")
            return {"status": "error", "message": "Population initialization failed."}

        fitnesses = list(map(toolbox.evaluate, population))
        for ind, fit in zip(population, fitnesses):
            ind.fitness.values = fit

        # Track early termination
        best_fitness = None
        no_progress_count = 0
        MAX_NO_PROGRESS = 10  # Terminate after 10 generations with no improvement

        for gen in range(GENERATIONS):
            logger.info(f"Generation {gen + 1}/{GENERATIONS}")

            # Select, crossover, and mutate the population
            offspring = toolbox.select(population, len(population))
            offspring = list(map(toolbox.clone, offspring))

            for child1, child2 in zip(offspring[::2], offspring[1::2]):
                toolbox.mate(child1, child2)
                del child1.fitness.values, child2.fitness.values

            for mutant in offspring:
                toolbox.mutate(mutant)
                del mutant.fitness.values

            # Evaluate invalid individuals
            invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
            fitnesses = map(toolbox.evaluate, invalid_ind)
            for ind, fit in zip(invalid_ind, fitnesses):
                ind.fitness.values = fit

            population[:] = offspring

            # Check the best fitness in the current generation
            best_in_gen = tools.selBest(population, 1)[0]
            logger.info(f"Best fitness in generation {gen + 1}: {best_in_gen.fitness.values[0]}")

            # Early termination check
            if best_fitness is None or best_in_gen.fitness.values[0] < best_fitness:
                best_fitness = best_in_gen.fitness.values[0]
                no_progress_count = 0
            else:
                no_progress_count += 1

            if no_progress_count >= MAX_NO_PROGRESS:
                logger.warning(f"No improvement for {MAX_NO_PROGRESS} generations. Terminating early.")
                break

        # Final best individual
        best_ind = tools.selBest(population, 1)[0]
        logger.info(f"Best individual's fitness: {best_ind.fitness.values[0]}")

        # Save the timetable
        for session in best_ind:
            if is_valid_session(session) and hasattr(session["subject"], "department"):
                try:
                    if isinstance(session["time_slot"], tuple):
                        for slot in session["time_slot"]:
                            Timetable.objects.create(
                                department=session["subject"].department,
                                faculty=None,
                                subject=session["subject"],
                                classroom=None,
                                time_slot=slot
                            )
                    else:
                        Timetable.objects.create(
                            department=session["subject"].department,
                            faculty=None,
                            subject=session["subject"],
                            classroom=None,
                            time_slot=session["time_slot"]
                        )
                except Exception as e:
                    logger.error(f"Error saving session: {e}")

    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

    logger.info("Timetable generation completed successfully.")
    return {"status": "success", "message": "Timetable generated successfully."}

