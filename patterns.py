import random


DURATIONS = [
    ("16", 0.25),  # sixteenth
    ("8", 0.5),    # eighth
    ("q", 1.0),    # quarter
    ("h", 2.0),    # half
]


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
