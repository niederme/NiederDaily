from copy import deepcopy
from datetime import date
import importlib
from unittest.mock import MagicMock

import pytest

from modules.opening_safety import calendar_kind, opening_rejection, package_context
from modules.welcome import opening_rejection_reason, welcome_block, validate_opening

DELIVERIES = [
    {"title": "Example Store - Carrier", "calendar": "Parcel", "time": "2:00pm", "end_time": "4:00pm", "all_day": False},
    {"title": "Other Store - Carrier", "calendar": "Parcel", "time": "2:00pm", "end_time": "4:00pm", "all_day": False},
]
REMINDERS = {"overdue": [{"title": "Check household supply", "list": "Household", "due": "2026-10-20"}]}
PACKAGES = {"freshness": "fresh", "shipments": [{"company": "Example Store", "item": "Jacket", "carrier_code": "carrier", "status": "out for delivery", "expected_delivery": {"date": "2026-11-11", "time": "14:00", "end_date": "2026-11-11", "end_time": "16:00", "timezone": None}}]}


@pytest.mark.parametrize("text", [
    "Two Carrier pickups at 2 anchor the afternoon.",
    "Stop at Example Store before dinner.",
    "Swing by Example Store.",
    "Fit Example Store in between meetings.",
    "The packages are coming. Grab them on the way.",
    "Your Carrier delivery arrives at 2.",
    "Call about the household supply before it becomes urgent.",
    "The household supply check is three weeks overdue, so it deserves a call.",
    "The household supply needs ordering.",
])
def test_rejects_delivery_and_reminder_inferences(text):
    assert validate_opening(text, calendar_events=DELIVERIES, reminders=REMINDERS, packages=PACKAGES) is None


@pytest.mark.parametrize("text", [
    "Example Store has an estimated delivery window of 2–4pm.",
    "The household supply reminder is listed below.",
    "The household supply reminder is overdue.",
])
def test_allows_neutral_source_facts(text):
    assert validate_opening(text, calendar_events=DELIVERIES, reminders=REMINDERS) == text


def test_explicit_separate_pickup_at_same_merchant_is_not_overridden():
    events = DELIVERIES + [{"title": "Pick up order at Example Store", "calendar": "Personal", "time": "11:00am"}]
    assert validate_opening("Pick up the order at Example Store.", calendar_events=events)
    assert calendar_kind({"title": "Meeting with Carrier", "calendar": "Work"}) != "delivery"
    assert calendar_kind({"title": "Example Store available for pickup", "calendar": "Parcel"}) == "pickup"


def test_explicit_call_reminder_is_allowed_without_invented_urgency():
    reminders = {"today": [{"title": "Call household supplier", "due": "2026-11-11"}]}
    assert validate_opening("Call the household supplier.", reminders=reminders)


def test_typed_prompt_preserves_source_and_estimate_without_mutation(mocker):
    client = MagicMock()
    client.messages.create.return_value.content = [MagicMock(text="Details are listed below.")]
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=client)
    events = deepcopy(DELIVERIES)
    packages = deepcopy(PACKAGES)
    packages["shipments"][0]["tracking_number"] = "PRIVATE_SENTINEL"
    welcome_block("fake", None, events, packages=packages, reminders=REMINDERS,
                  messages={"thread_count": 3, "summary": "UNRELIABLE_SENTINEL"})
    prompt = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "source calendar: Parcel; type: delivery" in prompt
    assert "estimated window 2:00pm–4:00pm" in prompt
    assert '"end_time": "16:00"' in prompt
    assert "PRIVATE_SENTINEL" not in prompt
    assert "UNRELIABLE_SENTINEL" not in prompt
    assert events == DELIVERIES
    assert package_context({**PACKAGES, "freshness": "stale"}) == []


def test_unknown_window_does_not_offer_start_as_an_exact_eta(mocker):
    client = MagicMock()
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=client)
    welcome_block("fake", None, [{"title": "Example Store", "calendar": "Parcel", "time": "2:00pm"}])
    prompt = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "delivery timing not established" in prompt
    assert "2:00pm" not in prompt




@pytest.mark.parametrize("text", [
    "Your household supply reminder is overdue, so it is urgent.",
    "Check household supply. Give them a call today.",
    "Check household supply. That deserves a call today.",
    "Check household supply. Urgent.",
    "Your Example Store delivery arrives at noon.",
    "Your Example Store delivery arrives by midnight.",
])
def test_review_regressions(text):
    assert validate_opening(text, calendar_events=DELIVERIES, reminders=REMINDERS) is None


def test_pickup_does_not_override_explicit_delivery_or_product_collection():
    events = DELIVERIES + [{"title": "Example Store pickup", "calendar": "Personal"}]
    assert validate_opening("Pick up the Example Store delivery on your way home.", calendar_events=events) is None
    assert calendar_kind({"title": "Winter collection delivery", "calendar": "Parcel"}) == "delivery"
    assert calendar_kind({"title": "Not ready for pickup", "calendar": "Parcel"}) == "delivery"


def test_generic_pickups_are_rejected_but_explicit_other_errand_is_allowed():
    assert validate_opening("The pickups anchor the afternoon.", calendar_events=DELIVERIES) is None
    events = DELIVERIES + [{"title": "Stop at hardware store", "calendar": "Personal"}]
    assert validate_opening("Stop at hardware store.", calendar_events=events)


@pytest.mark.parametrize("clock", ["2pm", "2 pm", "2:00pm", "2:00 pm", "noon", "midnight"])
def test_exact_delivery_time_with_meridiem_is_rejected(clock):
    assert validate_opening(f"Your Example Store delivery arrives at {clock}.", calendar_events=DELIVERIES) is None


def test_package_noun_does_not_join_same_merchant_pickup():
    events = DELIVERIES + [{"title": "Example Store pickup", "calendar": "Personal"}]
    assert validate_opening("Pick up the Example Store package on your way home.", calendar_events=events) is None


def test_orchestrator_passes_reminders_and_skips_messages(mocker):
    app = importlib.import_module("niederdaily")
    mocker.patch.object(app.cfg, "load_config", return_value={"anthropic_api_key": "fake", "recipient_email": "preview@example.invalid"})
    for name in ("weather_block", "calendar_block", "photo_block", "tweet_block", "nyt_block",
                 "live_packages_block"):
        mocker.patch.object(app, name, return_value=None)
    mocker.patch.object(app, "reminders_block", return_value=REMINDERS)
    messages = mocker.patch.object(app, "messages_block", side_effect=AssertionError("Messages must not run"))
    welcome = mocker.patch.object(app, "welcome_block", return_value=None)
    mocker.patch.object(app, "render_email", return_value=MagicMock())
    send = mocker.patch.object(app, "send_email", return_value=True)
    app.run()
    assert welcome.call_args.kwargs["reminders"] == REMINDERS
    messages.assert_not_called()
    send.assert_called_once()


# --- A package in transit must not taint unrelated sentences ---

IN_TRANSIT = {"freshness": "fresh", "shipments": [{"company": "Example Store", "item": "", "carrier_code": "carrier",
              "status": "in transit", "expected_delivery": {"date": "2026-11-18", "time": None,
                                                              "end_date": None, "end_time": None, "timezone": None}}]}


@pytest.mark.parametrize("text", [
    "The school play is at 11 this morning.",  # "11" came from the estimate's date, 2026-11-18
    "Leave some time for the play at 11.",  # "time" came from the estimate dict's keys
    "The game is on tonight; catch it at 8 if you are back.",  # bare "it" with no package named
    "The morning starts with an urgent care visit at 9:40.",  # "visit" is not a package errand
])
def test_package_in_transit_does_not_reject_unrelated_sentences(text):
    assert validate_opening(text, packages=IN_TRANSIT) == text


@pytest.mark.parametrize("text", [
    "Your Example Store package arrives at 2pm.",
    "A package is coming. It lands at 2pm.",  # the pronoun follows a sentence naming the package
    "Visit Example Store for the package.",
    "The pickups anchor the afternoon.",  # pickup wording still fails closed without a package named
])
def test_package_claims_still_rejected(text):
    assert validate_opening(text, packages=IN_TRANSIT) is None


@pytest.mark.parametrize("text", [
    "Both fit in the margins of a busy day.",
    "The school play is a highlight, not a casual errand.",
])
def test_soft_errand_wording_without_a_package_is_allowed(text):
    assert validate_opening(text, packages=IN_TRANSIT) == text


# --- Several reminders in one sentence ---

TODAY_REMINDERS = {"today": [{"title": "Call a relative", "list": "Personal", "due": "2026-11-14"},
                             {"title": "Talk to Alex about Thursday's schedule", "list": "Personal", "due": "2026-11-14"},
                             {"title": "Water the plants", "list": "Personal", "due": "2026-11-14"}]}


@pytest.mark.parametrize("text", [
    "Call a relative when you can, and talk to Alex about Thursday's schedule.",
    "A few things on the list: calling a relative, watering the plants, and Thursday's schedule with Alex.",
    "Water the plants after the urgent care stop.",  # a place, not urgency
])
def test_listing_several_reminders_keeps_their_own_actions(text):
    # The action check alone accepts these; the opening as a whole now allows one reminder.
    assert opening_rejection(text, [], TODAY_REMINDERS, None) is None


@pytest.mark.parametrize("text", [
    "Water the plants and order a new pot.",  # no reminder says order
    "Calling a relative is urgent today.",
])
def test_reminder_inventions_still_rejected_in_lists(text):
    assert validate_opening(text, reminders=TODAY_REMINDERS) is None


# --- A second reminder only counts when the draft uses words the prompt did not give it ---
MANY_REMINDERS = {
    "today": [{"title": "Get shrimp", "due": "2026-11-25", "list": "Groceries"}],
    "upcoming": [
        {"title": "Book home inspection", "due": "2026-11-30", "list": "House"},
        {"title": "Arena parking pass", "due": "2026-11-29", "list": "House"},
    ],
}
GAME_NIGHT = [{"title": "Visitors at Hosts", "time": "7:00 PM", "location": "Lakeside Arena"}]


def test_retelling_the_day_does_not_count_as_a_second_reminder():
    text = ("You're working from home today. The visitors play the hosts tonight at Lakeside Arena.\n\n"
            "The shrimp is on the list.")
    context = "LOCATION: home today. CALENDAR OPTIONS: Visitors at Hosts (evening; place: Lakeside Arena)."
    assert opening_rejection_reason(text, calendar_events=GAME_NIGHT, reminders=MANY_REMINDERS,
                                    prompt_context=context) is None


def test_event_place_alone_does_not_count_as_a_reminder():
    text = "The visitors play the hosts tonight at Lakeside Arena. The shrimp is on the list."
    assert opening_rejection_reason(text, calendar_events=GAME_NIGHT,
                                    reminders=MANY_REMINDERS) != "too_many_reminders"


def test_naming_a_reminder_the_prompt_never_gave_still_fails():
    text = "The shrimp is on the list, and so is the inspection."
    assert opening_rejection_reason(text, calendar_events=GAME_NIGHT, reminders=MANY_REMINDERS,
                                    prompt_context="LOCATION: home today.") == "too_many_reminders"
