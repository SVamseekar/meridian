import random

from faker import Faker


def seed_all(seed: int) -> Faker:
    """Seeds Faker and Python's random module separately — Faker's RNG is
    NOT seeded by random.seed() automatically (gotchas.md #1), so both
    calls are required for --seed reproducibility."""

    Faker.seed(seed)
    random.seed(seed)
    return Faker()
