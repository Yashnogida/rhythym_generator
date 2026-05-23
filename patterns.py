import random


DURATIONS = [
    ("16", 0.25),  # sixteenth
    ("8", 0.5),    # eighth
    ("q", 1.0),    # quarter
    ("h", 2.0),    # half
]

TUPLETS = {
    "Normal": {
        "subdivision": 4,
        "duration": "16",
        "tuplet_notes": None,
        "notes_occupied": None,
    },
    "Triplet": {
        "subdivision": 3,
        "duration": "8",
        "tuplet_notes": 3,
        "notes_occupied": 2,
    },
    "Quintuplet": {
        "subdivision": 5,
        "duration": "16",
        "tuplet_notes": 5,
        "notes_occupied": 4,
    },
    "Septuplet": {
        "subdivision": 7,
        "duration": "16",
        "tuplet_notes": 7,
        "notes_occupied": 4,
    },
}


PRESETS = {

    "Singles (16ᵗʰ Notes)": {
        "durations": [("16", 0.25)],
        "rest_chance": 0.0,
        "accent_chance": 0.25,
        "max_same_hand": 1,
    },
    
    "Max Doubles (16ᵗʰ Notes)": {
        "durations": [("16", 0.25)],
        "rest_chance": 0.0,
        "accent_chance": 0.25,
        "max_same_hand": 2,
    },

    "Doubles Only (16th Notes)": {
        "durations": [("16", 0.25)],
        "rest_chance": 0.0,
        "accent_chance": 0.25,
        "max_same_hand": 2,
        "sticking_rule": "doubles_only",
    },

    "Kick/Snare Mix (8th/16th Notes)": {
        "durations": [("16", 0.25), ("8", 0.5)],
        "rest_chance": 0.0,
        "accent_chance": 0.0,
        "instruments": ["kick", "snare"],
        "staff": "drumset",
    },

    "Kick/Snare/Ride Mix": {
        "durations": [("16", 0.25), ("8", 0.5)],
        "rest_chance": 0.0,
        "accent_chance": 0.0,
        "instruments": ["kick", "snare"],
        "simultaneous_ride_chance": 0.35,
        "staff": "drumset",
    },


}


def preset_names():
    return list(PRESETS.keys())


def generate_pattern(numerator, denominator, preset_name):
    beats = numerator * (4 / denominator)
    preset = PRESETS[preset_name]

    return [generate_valid_measure(beats, preset)]


def generate_drum_exercise(numerator, denominator, drum_options, tuplet_name="Normal"):
    tuplet = TUPLETS[tuplet_name]
    slots = int(numerator * (4 / denominator) * tuplet["subdivision"])
    snare_only = is_snare_only_exercise(drum_options)

    for _ in range(1000):
        measure = generate_drum_measure(slots, drum_options, snare_only, tuplet)
        if follows_drum_options(measure, drum_options):
            return [measure]

    return [measure]


def is_snare_only_exercise(drum_options):
    return (
        len(drum_options) == 1
        and drum_options[0]["instrument"] == "snare"
    )


def generate_drum_measure(slots, drum_options, snare_only, tuplet):
    notes = []
    hand_histories = {
        option["instrument"]: []
        for option in drum_options
    }
    only_groups = {
        option["instrument"]: {
            "hand": random.choice(["L", "R"]),
            "remaining": 0,
        }
        for option in drum_options
        if option["type"] == "only"
    }

    while len(notes) < slots:
        remaining_slots = slots - len(notes)
        option = choose_drum_option(drum_options, only_groups, remaining_slots)
        instrument = option["instrument"]
        hand = choose_drum_hand(option, hand_histories[instrument], only_groups)

        notes.append(build_drum_note(instrument, hand, snare_only, tuplet))

    return notes


def choose_drum_option(drum_options, only_groups, remaining_slots):
    active_only_options = [
        option
        for option in drum_options
        if (
            option["type"] == "only"
            and only_groups[option["instrument"]]["remaining"] > 0
        )
    ]

    if active_only_options:
        return random.choice(active_only_options)

    possible_options = [
        option
        for option in drum_options
        if option["type"] == "max" or option["strokes"] <= remaining_slots
    ]

    return random.choice(possible_options or drum_options)


def choose_drum_hand(option, hand_history, only_groups):
    if option["type"] == "only":
        group = only_groups[option["instrument"]]

        if group["remaining"] == 0:
            if hand_history:
                group["hand"] = "L" if hand_history[-1] == "R" else "R"
            group["remaining"] = option["strokes"]

        hand = group["hand"]
        group["remaining"] -= 1
        hand_history.append(hand)
        return hand

    return choose_hand(hand_history, option["strokes"])


def build_drum_note(instrument, hand, snare_only, tuplet):
    note = {
        "duration": tuplet["duration"],
        "keys": instrument_keys(instrument),
        "instrument": instrument,
        "stroke_hand": hand,
        "play_value": 1 / tuplet["subdivision"],
        "accented": instrument == "snare" and random.random() < 0.25,
    }

    if instrument == "snare":
        note["hand"] = hand

    if not snare_only:
        note["staff"] = "drumset"

    return note


def follows_drum_options(measure, drum_options):
    for option in drum_options:
        if option["instrument"] != "snare":
            instrument_run_lengths = consecutive_instrument_run_lengths(
                measure,
                option["instrument"],
            )

            if not instrument_run_lengths:
                continue

            if option["type"] == "only":
                if any(length != option["strokes"] for length in instrument_run_lengths):
                    return False
            elif any(length > option["strokes"] for length in instrument_run_lengths):
                return False

            continue

        snare_hands = [
            note["stroke_hand"]
            for note in measure
            if note.get("instrument") == "snare"
        ]

        if not snare_hands:
            continue

        if option["type"] == "only":
            if not follows_only_stroke_rule(snare_hands, option["strokes"]):
                return False
        elif not follows_hand_sequence_rule(snare_hands, option["strokes"]):
            return False

    return True


def consecutive_instrument_run_lengths(measure, instrument):
    run_lengths = []
    current_run = 0

    for note in measure:
        if note.get("instrument") == instrument:
            current_run += 1
        elif current_run:
            run_lengths.append(current_run)
            current_run = 0

    if current_run:
        run_lengths.append(current_run)

    return run_lengths


def follows_only_stroke_rule(hands, strokes):
    if len(hands) % strokes != 0:
        return False

    previous_group_hand = None
    first_group_hand = None

    for index in range(0, len(hands), strokes):
        group = hands[index:index + strokes]
        if len(set(group)) != 1:
            return False

        group_hand = group[0]
        if first_group_hand is None:
            first_group_hand = group_hand

        if previous_group_hand == group_hand:
            return False

        previous_group_hand = group_hand

    if previous_group_hand == first_group_hand:
        return False

    return True


def follows_hand_sequence_rule(hands, max_same_hand):
    if len(hands) <= max_same_hand:
        return True

    looped_hands = hands + hands[:max_same_hand]
    same_hand_count = 1

    for previous_hand, current_hand in zip(looped_hands, looped_hands[1:]):
        if current_hand == previous_hand:
            same_hand_count += 1
            if same_hand_count > max_same_hand:
                return False
        else:
            same_hand_count = 1

    return True


def generate_valid_measure(beats, preset):
    for _ in range(1000):
        hand_history = []
        measure = generate_measure(beats, preset, hand_history)
        if preset.get("sticking_rule") == "doubles_only":
            if follows_doubles_only_rule(measure):
                return measure
            continue

        if "max_same_hand" not in preset:
            return measure

        if follows_looping_sticking_rule(measure, preset["max_same_hand"]):
            return measure

    return measure


def generate_measure(beats, preset, hand_history):
    notes = []
    remaining = beats

    while remaining > 0:
        possible = [
            (name, value)
            for name, value in preset["durations"]
            if value <= remaining + 0.001
        ]
        dur_name, dur_value = random.choice(possible)
        is_rest = random.random() < preset["rest_chance"]

        note = build_note(dur_name, is_rest, preset)

        if not is_rest:
            if preset.get("instruments"):
                note["instrument"] = random.choice(preset["instruments"])
                note["keys"] = instrument_keys(note["instrument"])
                if random.random() < preset.get("simultaneous_ride_chance", 0.0):
                    note["keys"] += instrument_keys("ride")
                    note["instrument"] += "+ride"
            elif preset.get("sticking_rule") == "doubles_only":
                note["hand"] = choose_doubles_only_hand(len(notes), hand_history)
            else:
                note["hand"] = choose_hand(hand_history, preset["max_same_hand"])
            note["accented"] = random.random() < preset["accent_chance"]

        notes.append(note)
        remaining = round(remaining - dur_value, 2)

    accentable_notes = [note for note in notes if "hand" in note]
    if (
        preset["accent_chance"] > 0
        and accentable_notes
        and not any(note.get("accented") for note in accentable_notes)
    ):
        random.choice(accentable_notes)["accented"] = True

    return notes


def build_note(duration, is_rest, preset):
    note = {
        "duration": duration + ("r" if is_rest else ""),
        "keys": ["b/4"] if is_rest else ["c/5"],
    }

    if preset.get("staff") == "drumset":
        note["staff"] = "drumset"

    return note


def instrument_keys(instrument):
    if instrument == "kick":
        return ["f/4"]
    if instrument == "ride":
        return ["g/5"]
    if instrument == "hihat":
        return ["f/5"]

    return ["c/5"]


def choose_hand(hand_history, max_same_hand):
    if len(hand_history) >= max_same_hand:
        recent_hands = hand_history[-max_same_hand:]
        if len(set(recent_hands)) == 1:
            hand = "L" if recent_hands[0] == "R" else "R"
            hand_history.append(hand)
            return hand

    hand = random.choice(["L", "R"])
    hand_history.append(hand)
    return hand


def choose_doubles_only_hand(note_index, hand_history):
    if note_index % 2 == 0:
        if not hand_history:
            hand = random.choice(["L", "R"])
        else:
            hand = "L" if hand_history[-1] == "R" else "R"
    else:
        hand = hand_history[-1]

    hand_history.append(hand)
    return hand


def follows_looping_sticking_rule(measure, max_same_hand):
    hands = [note["hand"] for note in measure if "hand" in note]

    if not hands:
        return True

    doubled_hands = hands + hands[:max_same_hand]
    same_hand_count = 1

    for previous_hand, current_hand in zip(doubled_hands, doubled_hands[1:]):
        if current_hand == previous_hand:
            same_hand_count += 1
            if same_hand_count > max_same_hand:
                return False
        else:
            same_hand_count = 1

    return True


def follows_doubles_only_rule(measure):
    hands = [note["hand"] for note in measure if "hand" in note]

    if len(hands) % 2 != 0:
        return False

    for index in range(0, len(hands), 2):
        if hands[index] != hands[index + 1]:
            return False

    return follows_looping_sticking_rule(measure, 2)
