"""Effective policy and calendar lookup (BR-EL-030, BR-EL-031, SRS-EL-089..093)."""
from datetime import date

from django.db import transaction

from modules.elm.models import HolidayCalendar, LeavePolicy, PublishState

REQUIRED_KEYS = ("CL", "RH", "SCL", "EL", "COL", "VL")

DEFAULT_PARAMS = {"CL": 8, "RH": 2, "SCL": 15, "EL": 30, "COL": 20, "VL": 60,
                  "VL_PER_EL": 2}


class PolicyError(Exception):
    pass


class NoPublishedPolicy(PolicyError):
    pass


class NoPublishedCalendar(PolicyError):
    pass


def validate_params(params: dict) -> None:
    for key in REQUIRED_KEYS:
        value = params.get(key)
        if not isinstance(value, (int, float)) or value < 0:
            raise PolicyError(f"Policy parameter {key} must be a non-negative number.")


def get_effective_policy(on: date | None = None) -> LeavePolicy:
    """Latest published version already in force on the given date."""
    on = on or date.today()
    policy = (
        LeavePolicy.objects.filter(status=PublishState.PUBLISHED)
        .exclude(effective_from__gt=on)
        .order_by("-version")
        .first()
    )
    if policy is None:
        raise NoPublishedPolicy("No published leave policy is in force.")
    return policy


@transaction.atomic
def publish_policy(policy: LeavePolicy) -> LeavePolicy:
    """Validate first; the old policy stays in force if validation fails."""
    validate_params(policy.params)
    LeavePolicy.objects.filter(status=PublishState.PUBLISHED).exclude(pk=policy.pk).update(
        status=PublishState.RETIRED
    )
    policy.status = PublishState.PUBLISHED
    policy.save(update_fields=["status", "updated_at"])
    return policy


def get_effective_calendar(year: int) -> HolidayCalendar:
    cal = (
        HolidayCalendar.objects.filter(year=year, status=PublishState.PUBLISHED)
        .order_by("-version")
        .first()
    )
    if cal is None:
        raise NoPublishedCalendar(f"No published holiday calendar for {year}.")
    return cal


@transaction.atomic
def publish_calendar(calendar: HolidayCalendar) -> HolidayCalendar:
    HolidayCalendar.objects.filter(year=calendar.year, status=PublishState.PUBLISHED).exclude(
        pk=calendar.pk
    ).update(status=PublishState.RETIRED)
    calendar.status = PublishState.PUBLISHED
    calendar.save(update_fields=["status", "updated_at"])
    return calendar