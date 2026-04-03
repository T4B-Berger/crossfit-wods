from __future__ import annotations

from functools import lru_cache

# Deterministic canonical movement taxonomy used by parser normalization.
# Includes the movements currently supported by parser aliases and extraction.
MOVEMENT_TAXONOMY = {
    "schema_version": "1.0",
    "families": ["engine", "gymnastics", "weightlifting", "strongman"],
    "patterns": [
        "cyclic", "squat", "hinge", "push", "pull", "core", "full_body", "inverted",
        "carry", "lunge", "jump", "throw", "climb", "skill",
    ],
    "implements": [
        "bodyweight", "barbell", "dumbbell", "kettlebell", "medball", "machine", "jump_rope",
        "box", "rope", "rings", "rig", "bench", "ghd", "sled", "yoke", "other",
    ],
    "skill_levels": ["beginner", "intermediate", "advanced"],
    "movements": [
        {"id": "run", "name": "Run", "family": "engine", "patterns": ["cyclic"], "implement": "other", "skill_level": "beginner"},
        {"id": "row", "name": "Row", "family": "engine", "patterns": ["cyclic"], "implement": "machine", "skill_level": "beginner"},
        {"id": "double_under", "name": "Double Under", "family": "engine", "patterns": ["cyclic", "jump"], "implement": "jump_rope", "skill_level": "intermediate"},
        {"id": "air_squat", "name": "Air Squat", "family": "gymnastics", "patterns": ["squat"], "implement": "bodyweight", "skill_level": "beginner"},
        {"id": "walking_lunge", "name": "Walking Lunge", "family": "gymnastics", "patterns": ["lunge"], "implement": "bodyweight", "skill_level": "beginner"},
        {"id": "box_jump", "name": "Box Jump", "family": "gymnastics", "patterns": ["jump"], "implement": "box", "skill_level": "beginner"},
        {"id": "box_jump_over", "name": "Box Jump Over", "family": "gymnastics", "patterns": ["jump", "full_body"], "implement": "box", "skill_level": "intermediate"},
        {"id": "burpee", "name": "Burpee", "family": "gymnastics", "patterns": ["push", "full_body"], "implement": "bodyweight", "skill_level": "beginner"},
        {"id": "push_up", "name": "Push-Up", "family": "gymnastics", "patterns": ["push"], "implement": "bodyweight", "skill_level": "beginner"},
        {"id": "pull_up", "name": "Pull-Up", "family": "gymnastics", "patterns": ["pull"], "implement": "rig", "skill_level": "intermediate"},
        {"id": "toes_to_bar", "name": "Toes-to-Bar", "family": "gymnastics", "patterns": ["core", "pull"], "implement": "rig", "skill_level": "intermediate"},
        {"id": "muscle_up", "name": "Muscle-Up", "family": "gymnastics", "patterns": ["pull", "push", "full_body"], "implement": "rings", "skill_level": "advanced"},
        {"id": "sit_up", "name": "Sit-Up", "family": "gymnastics", "patterns": ["core"], "implement": "bodyweight", "skill_level": "beginner"},
        {"id": "handstand_push_up", "name": "Handstand Push-Up", "family": "gymnastics", "patterns": ["push", "inverted"], "implement": "bodyweight", "skill_level": "advanced"},
        {"id": "back_squat", "name": "Back Squat", "family": "weightlifting", "patterns": ["squat"], "implement": "barbell", "skill_level": "beginner"},
        {"id": "front_squat", "name": "Front Squat", "family": "weightlifting", "patterns": ["squat"], "implement": "barbell", "skill_level": "beginner"},
        {"id": "overhead_squat", "name": "Overhead Squat", "family": "weightlifting", "patterns": ["squat", "full_body"], "implement": "barbell", "skill_level": "advanced"},
        {"id": "deadlift", "name": "Deadlift", "family": "weightlifting", "patterns": ["hinge"], "implement": "barbell", "skill_level": "beginner"},
        {"id": "sumo_deadlift_high_pull", "name": "Sumo Deadlift High Pull", "family": "weightlifting", "patterns": ["hinge", "pull", "full_body"], "implement": "barbell", "skill_level": "intermediate"},
        {"id": "bench_press", "name": "Bench Press", "family": "weightlifting", "patterns": ["push"], "implement": "bench", "skill_level": "beginner"},
        {"id": "push_press", "name": "Push Press", "family": "weightlifting", "patterns": ["push", "full_body"], "implement": "barbell", "skill_level": "beginner"},
        {"id": "push_jerk", "name": "Push Jerk", "family": "weightlifting", "patterns": ["push", "full_body"], "implement": "barbell", "skill_level": "intermediate"},
        {"id": "split_jerk", "name": "Split Jerk", "family": "weightlifting", "patterns": ["push", "full_body"], "implement": "barbell", "skill_level": "advanced"},
        {"id": "clean", "name": "Clean", "family": "weightlifting", "patterns": ["hinge", "pull", "full_body"], "implement": "barbell", "skill_level": "advanced"},
        {"id": "power_clean", "name": "Power Clean", "family": "weightlifting", "patterns": ["hinge", "pull", "full_body"], "implement": "barbell", "skill_level": "intermediate"},
        {"id": "hang_power_clean", "name": "Hang Power Clean", "family": "weightlifting", "patterns": ["hinge", "pull", "full_body"], "implement": "barbell", "skill_level": "intermediate"},
        {"id": "snatch", "name": "Snatch", "family": "weightlifting", "patterns": ["hinge", "pull", "full_body"], "implement": "barbell", "skill_level": "advanced"},
        {"id": "power_snatch", "name": "Power Snatch", "family": "weightlifting", "patterns": ["hinge", "pull", "full_body"], "implement": "barbell", "skill_level": "advanced"},
        {"id": "hang_power_snatch", "name": "Hang Power Snatch", "family": "weightlifting", "patterns": ["hinge", "pull", "full_body"], "implement": "barbell", "skill_level": "advanced"},
        {"id": "clean_and_jerk", "name": "Clean and Jerk", "family": "weightlifting", "patterns": ["hinge", "pull", "push", "full_body"], "implement": "barbell", "skill_level": "advanced"},
        {"id": "thruster", "name": "Thruster", "family": "weightlifting", "patterns": ["squat", "push", "full_body"], "implement": "barbell", "skill_level": "beginner"},
        {"id": "wall_ball", "name": "Wall Ball", "family": "weightlifting", "patterns": ["squat", "throw", "full_body"], "implement": "medball", "skill_level": "beginner"},
        {"id": "kettlebell_swing", "name": "Kettlebell Swing", "family": "weightlifting", "patterns": ["hinge", "full_body"], "implement": "kettlebell", "skill_level": "beginner"},
    ],
}


@lru_cache(maxsize=1)
def movement_index() -> dict[str, dict]:
    return {m["id"]: m for m in MOVEMENT_TAXONOMY["movements"]}
