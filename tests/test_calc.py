"""Test della formula e dei giorni di irrigazione."""

from datetime import datetime

from custom_components.irrigazione_ai.calc import calculate_duration, is_irrigation_day


def test_formula_matches_legacy_template() -> None:
    """Stessi risultati dei vecchi sensori template."""
    # u=47%, T=7.4, rainy -> (20 + 20*53/47 + 20*7.4/25)*0.9*0.2 = 9.4 -> min 15
    assert calculate_duration(47, 7.4, "rainy") == 15
    # u=30%, T=25, sunny -> (20 + 46.67 + 20)*0.9*1.1 = 85.8
    assert calculate_duration(30, 25, "sunny") == 86
    # u=40%, T=20, cloudy -> (20 + 30 + 16)*0.9*0.5 = 29.7
    assert calculate_duration(40, 20, "cloudy") == 30


def test_formula_moisture_floor_and_clamp() -> None:
    """Umidità 0 non divide per zero; massimo rispettato."""
    assert calculate_duration(0, 30, "sunny") == 120
    assert calculate_duration(None, None, None, min_minutes=1) == 50


def test_coefficient() -> None:
    """Il coefficiente scala il tempo."""
    base = calculate_duration(40, 20, "cloudy")
    assert calculate_duration(40, 20, "cloudy", coefficient=2) == round(29.7 * 2)
    assert base == 30


def test_irrigation_days() -> None:
    """Frequenze."""
    thursday = datetime(2026, 11, 19, 17, 0)
    friday = datetime(2026, 11, 20, 17, 0)
    sunday = datetime(2026, 11, 22, 17, 0)
    days = ["thu", "sun"]
    assert is_irrigation_day(thursday, "twice_weekly", "sun", days)
    assert not is_irrigation_day(friday, "twice_weekly", "sun", days)
    assert is_irrigation_day(sunday, "weekly", "sun", days)
    assert not is_irrigation_day(thursday, "weekly", "sun", days)
    assert is_irrigation_day(friday, "daily", "sun", days)
    assert not is_irrigation_day(sunday, "off", "sun", days)
