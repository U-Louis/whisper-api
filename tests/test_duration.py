from app.audio import check_duration
from app.errors import TooLong, UnreadableAudio


def test_thirty_seconds_is_accepted() -> None:
    check_duration(30, 30)


def test_just_over_thirty_seconds_is_too_long() -> None:
    try:
        check_duration(30.001, 30)
    except TooLong:
        return
    raise AssertionError("expected TooLong")


def test_non_positive_duration_is_unreadable() -> None:
    for value in (0, -1, float("nan"), float("inf")):
        try:
            check_duration(value, 30)
        except UnreadableAudio:
            continue
        raise AssertionError(value)
