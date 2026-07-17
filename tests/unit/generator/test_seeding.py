import random

from faker import Faker

from data.generator.seeding import seed_all


def test_seed_all_returns_faker_instance():
    fake = seed_all(42)
    assert isinstance(fake, Faker)


def test_seed_all_is_deterministic_for_faker():
    fake1 = seed_all(42)
    value1 = fake1.company()

    fake2 = seed_all(42)
    value2 = fake2.company()

    assert value1 == value2


def test_seed_all_is_deterministic_for_random_module():
    seed_all(42)
    value1 = random.random()

    seed_all(42)
    value2 = random.random()

    assert value1 == value2
