from typing import Any, Optional

import factory
from demo.models import Job, MultipleJob
from django.contrib.auth.models import Group, Permission, User
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


class AsyncJobModelFactory(DjangoModelFactory):
    curr_async_result_id = None
    last_async_result_id = None

    class Meta:
        model = MultipleJob


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User


class GroupFactory(DjangoModelFactory):
    name = Faker("name")

    class Meta:
        model = Group
        django_get_or_create = ("name",)
        skip_postgeneration_save = True

    @factory.post_generation  # type: ignore[misc]
    def permissions(self, create: bool, extracted: list[str], **kwargs: Any) -> None:
        if not create:
            # Simple build, do nothing.
            return

        if extracted:
            for perm_name in extracted:
                app, perm = perm_name.split(".")
                self.permissions.add(
                    Permission.objects.get(content_type__app_label=app, codename=perm)
                )

    @classmethod
    def _after_postgeneration(cls, instance, create, results=None):
        if create and results and not cls._meta.skip_postgeneration_save:
            instance.save()


class user_grant_permission:
    def __init__(self, user: User, permissions: Optional[list[str]] = None):
        self.user = user
        self.permissions = permissions
        self.group = None

    def __enter__(self):
        if hasattr(self.user, "_group_perm_cache"):
            del self.user._group_perm_cache
        if hasattr(self.user, "_perm_cache"):
            del self.user._perm_cache
        self.group = GroupFactory(permissions=self.permissions or [])
        self.user.groups.add(self.group)

    def __exit__(self, *exc_info):
        if self.group:
            self.user.groups.remove(self.group)
            self.group.delete()

    def start(self):
        """Activate a patch, returning any created mock."""
        result = self.__enter__()
        return result

    def stop(self):
        """Stop an active patch."""
        return self.__exit__()
