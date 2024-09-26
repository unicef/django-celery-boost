from demo.models import Job
from factory.django import DjangoModelFactory
from factory.faker import Faker
from factory.fuzzy import FuzzyInteger


class JobFactory(DjangoModelFactory):
    name = Faker("name")
    number = FuzzyInteger(0, 200)
    curr_async_result_id = None
    last_async_result_id = None

    class Meta:
        model = Job
