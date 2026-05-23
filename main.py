import json
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl, Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QLabel, QLineEdit, QMessageBox, QWidget, QHBoxLayout, QVBoxLayout, QPushButton
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWebEngineWidgets import QWebEngineView

from patterns import generate_drum_exercise


NOTE_VALUES = {
    "16": 0.25,
    "8": 0.5,
    "q": 1.0,
    "h": 2.0,
}
BPM = 90


def make_html(pattern, numerator, denominator):
    pattern_json = json.dumps(pattern)

    return f"""
<!DOCTYPE html>
<html>
<head>
    <script src="https://cdn.jsdelivr.net/npm/vexflow@4.2.3/build/cjs/vexflow.min.js"></script>
    <style>
        body {{
            background: #ffffff;
            margin: 0;
            overflow: hidden;
        }}

        #notation {{
            box-sizing: border-box;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 8px 18px;
            width: 100vw;
            height: 100vh;
        }}
    </style>
</head>
<body>
    <div id="notation"></div>

    <script>
        const VF = Vex.Flow;
        const pattern = {pattern_json};

        const div = document.getElementById("notation");
        const renderer = new VF.Renderer(div, VF.Renderer.Backends.SVG);

        const measureWidth = 400;
        const rendererWidth = Math.max(
            div.clientWidth || 900,
            (measureWidth * pattern.length) + 40
        );
        const rendererHeight = window.innerHeight || 130;

        renderer.resize(rendererWidth, rendererHeight);

        const context = renderer.getContext();
        context.setFont("Arial", 10);
        const usesDrumsetStaff = pattern.some(measure =>
            measure.some(note => note.staff === "drumset")
        );

        let x = (rendererWidth - (measureWidth * pattern.length)) / 2;

        for (let i = 0; i < pattern.length; i++) {{
            const staveOptions = usesDrumsetStaff ? {{}} : {{ num_lines: 1 }};
            const staveY = usesDrumsetStaff ? 8 : 20;
            const stave = new VF.Stave(x, staveY, measureWidth, staveOptions);

            if (i === 0) {{
                stave.addTimeSignature("{numerator}/{denominator}");
            }}

            stave.setContext(context).draw();

            const notes = pattern[i].map(n => {{
                const note = new VF.StaveNote({{
                    clef: "percussion",
                    keys: n.keys,
                    duration: n.duration,
                    stem_direction: VF.Stem.UP
                }});
                note.setStemDirection(VF.Stem.UP);

                if (n.hand) {{
                    note.addModifier(new VF.Annotation(n.hand)
                        .setFont("Arial", 13, "bold")
                        .setVerticalJustification(VF.Annotation.VerticalJustify.BOTTOM));
                }}

                if (n.accented) {{
                    note.addModifier(new VF.Articulation("a>")
                        .setPosition(VF.Modifier.Position.ABOVE));
                }}

                return note;
            }});

            const voice = new VF.Voice({{
                num_beats: {numerator},
                beat_value: {denominator}
            }});

            voice.addTickables(notes);
            const beams = VF.Beam.generateBeams(notes, {{
                stem_direction: VF.Stem.UP
            }});

            new VF.Formatter()
                .joinVoices([voice])
                .format([voice], 320);

            voice.draw(context, stave);

            beams.forEach(beam => {{
                beam.setContext(context).draw();
            }});

            x += measureWidth;
        }}
    </script>
</body>
</html>
"""


class RhythmApp(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Rhythym Generator")
        self.resize(870, 840)
        self.setFixedSize(870, 840)

        self.web_views = []
        self.time_signature_inputs = []
        self.tuplet_inputs = []
        self.instrument_controls = []
        self.current_patterns = []
        self.play_timers = []
        self.play_buttons = []
        self.playing_index = None
        self.sounds = self.load_sounds()

        layout = QVBoxLayout()

        for pattern_number in range(6):
            row = QWidget()
            row.setFixedHeight(130)

            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(0, 5, 0, 5)

            web = QWebEngineView()
            web.setFixedHeight(130)

            pattern_label = QLabel(f"Pattern {pattern_number + 1}")
            pattern_label.setFixedWidth(150)

            button = QPushButton("Generate")
            button.setFixedWidth(100)
            button.clicked.connect(
                lambda checked=False, index=pattern_number: self.generate(index)
            )

            play_button = QPushButton("Play")
            play_button.setFixedWidth(100)
            play_button.clicked.connect(
                lambda checked=False, index=pattern_number: self.play(index)
            )

            numerator_input = QLineEdit("2")
            numerator_input.setValidator(QIntValidator(1, 16))
            numerator_input.setFixedWidth(43)

            denominator_input = QLineEdit("4")
            denominator_input.setValidator(QIntValidator(1, 16))
            denominator_input.setFixedWidth(43)

            tuplet_input = QComboBox()
            tuplet_input.addItems(["Normal", "Triplet", "Quintuplet", "Septuplet"])
            tuplet_input.setFixedWidth(100)

            time_signature_layout = QHBoxLayout()
            time_signature_layout.setContentsMargins(0, 0, 0, 0)
            time_signature_layout.setSpacing(4)
            time_signature_layout.addWidget(numerator_input)
            time_signature_layout.addWidget(QLabel("/"))
            time_signature_layout.addWidget(denominator_input)
            time_signature_layout.addStretch()

            # Left controls panel
            left_controls = QWidget()
            left_controls_layout = QVBoxLayout()
            left_controls_layout.setContentsMargins(0, 5, 0, 5)
            left_controls_layout.addWidget(pattern_label)
            left_controls_layout.addLayout(time_signature_layout)
            left_controls_layout.addWidget(tuplet_input)
            left_controls_layout.addWidget(play_button)
            left_controls_layout.addWidget(button)
            left_controls_layout.addStretch()
            left_controls.setLayout(left_controls_layout)

            # Instrument checkboxes
            instruments_widget = QWidget()
            instruments_layout = QVBoxLayout()
            instruments_layout.setContentsMargins(0, 15, 0, 0)
            instruments_layout.setSpacing(0)

            instruments_layout.addStretch()

            # Header row for Strokes label
            header_row = QWidget()
            header_layout = QHBoxLayout()
            header_layout.setContentsMargins(0, 0, 0, 0)
            header_layout.setSpacing(5)
            header_layout.addSpacing(30)  # Label width
            header_layout.addSpacing(20)  # Checkbox width
            header_layout.addSpacing(15)  # Additional spacing
            strokes_label = QLabel("Strokes")
            header_layout.addWidget(strokes_label)
            header_layout.addSpacing(15)  # Spacing before Type
            type_label = QLabel("Type")
            header_layout.addWidget(type_label)
            header_layout.addStretch()
            header_row.setLayout(header_layout)
            instruments_layout.addWidget(header_row)

            instrument_controls = {}
            for instrument in ["Snare", "Kick", "Hihat", "Ride"]:
                instrument_row = QWidget()
                instrument_row_layout = QHBoxLayout()
                instrument_row_layout.setContentsMargins(0, 0, 35, 0)
                instrument_row_layout.setSpacing(5)
                
                label = QLabel(instrument)
                label.setFixedWidth(30)                
                label.setAlignment(Qt.AlignRight)                
                checkbox = QCheckBox()
                checkbox.setChecked(instrument == "Snare")
                checkbox.setFixedWidth(20)
                
                value_box = QComboBox()
                value_box.addItems(["1", "2", "3", "4"])
                value_box.setFixedWidth(50)
                value_box.setCurrentIndex(0)  # Default to "1"
                value_box.setEnabled(checkbox.isChecked())
                
                type_box = QComboBox()
                type_box.addItems(["Only", "Max"])
                type_box.setFixedWidth(75)
                type_box.setEnabled(checkbox.isChecked())
                
                checkbox.toggled.connect(value_box.setEnabled)
                checkbox.toggled.connect(type_box.setEnabled)
                instrument_controls[instrument] = {
                    "checkbox": checkbox,
                    "strokes": value_box,
                    "type": type_box,
                }
                
                instrument_row_layout.addWidget(label)
                instrument_row_layout.addWidget(checkbox)
                instrument_row_layout.addWidget(value_box)
                instrument_row_layout.addWidget(type_box)
                instrument_row_layout.addStretch()
                
                instrument_row.setLayout(instrument_row_layout)
                instruments_layout.addWidget(instrument_row)

            instruments_layout.addStretch()
            instruments_widget.setLayout(instruments_layout)
            self.instrument_controls.append(instrument_controls)

            # Combined controls widget
            controls = QWidget()
            controls.setFixedWidth(340)
            controls_layout = QHBoxLayout()
            controls_layout.setContentsMargins(0, 0, 0, 0)
            controls_layout.setSpacing(0)
            controls_layout.addWidget(left_controls)
            controls_layout.addWidget(instruments_widget)
            controls.setLayout(controls_layout)

            self.web_views.append(web)
            self.time_signature_inputs.append((numerator_input, denominator_input))
            self.tuplet_inputs.append(tuplet_input)
            self.current_patterns.append([])
            self.play_buttons.append(play_button)

            row_layout.addWidget(controls)
            row_layout.addWidget(web)
            row.setLayout(row_layout)
            layout.addWidget(row)

        self.setLayout(layout)

        for pattern_number in range(6):
            self.generate(pattern_number)

    def generate(self, index):
        numerator, denominator = self.get_time_signature(index)
        drum_options = self.get_drum_options(index)
        error = self.validate_drum_options(numerator, denominator, drum_options)

        if error:
            QMessageBox.warning(self, "Cannot generate exercise", error)
            return

        pattern = generate_drum_exercise(numerator, denominator, drum_options)
        self.current_patterns[index] = pattern
        html = make_html(pattern, numerator, denominator)
        self.web_views[index].setHtml(html)

    def get_drum_options(self, index):
        options = []

        for instrument, controls in self.instrument_controls[index].items():
            if not controls["checkbox"].isChecked():
                continue

            options.append({
                "instrument": instrument.lower(),
                "strokes": int(controls["strokes"].currentText()),
                "type": controls["type"].currentText().lower(),
            })

        return options

    def validate_drum_options(self, numerator, denominator, drum_options):
        if not drum_options:
            return "Select at least one drum."

        slots = numerator * (16 / denominator)
        if slots != int(slots):
            return "This time signature does not divide evenly into 16th notes."

        slots = int(slots)
        invalid_only_options = [
            option
            for option in drum_options
            if option["type"] == "only" and slots % option["strokes"] != 0
        ]

        if invalid_only_options:
            descriptions = [
                f"{option['instrument'].title()} Only {option['strokes']}"
                for option in invalid_only_options
            ]
            return (
                f"This exercise has {slots} 16th notes, so "
                f"{', '.join(descriptions)} cannot fill it evenly."
            )

        return ""

    def load_sounds(self):
        sample_dir = Path(__file__).resolve().parent / "samples"
        sound_files = {
            "kick": "kick.wav",
            "snare": "snare.wav",
            "ride": "ride.wav",
            "stick": "stick.wav",
        }
        sounds = {}

        for name, file_name in sound_files.items():
            sound = QSoundEffect(self)
            sound.setSource(QUrl.fromLocalFile(str(sample_dir / file_name)))
            sound.setVolume(0.85)
            sounds[name] = sound

        return sounds

    def play(self, index):
        if self.playing_index == index:
            self.stop_playback()
            return

        self.stop_playback()

        if not self.current_patterns[index]:
            self.generate(index)

        self.playing_index = index
        self.play_buttons[index].setText("Stop")
        self.schedule_pattern(index)

    def schedule_pattern(self, index):
        seconds_per_quarter = 60 / BPM
        elapsed_ms = 0

        for measure in self.current_patterns[index]:
            for note in measure:
                sounds = self.sounds_for_note(note)
                if sounds:
                    timer = QTimer(self)
                    timer.setSingleShot(True)
                    timer.timeout.connect(
                        lambda sound_names=sounds: self.play_sounds(sound_names)
                    )
                    timer.start(elapsed_ms)
                    self.play_timers.append(timer)

                duration_name = note["duration"].rstrip("r")
                elapsed_ms += round(NOTE_VALUES[duration_name] * seconds_per_quarter * 1000)

        loop_timer = QTimer(self)
        loop_timer.setSingleShot(True)
        loop_timer.timeout.connect(lambda index=index: self.restart_loop(index))
        loop_timer.start(elapsed_ms)
        self.play_timers.append(loop_timer)

    def restart_loop(self, index):
        if self.playing_index != index:
            return

        self.clear_play_timers()
        self.schedule_pattern(index)

    def stop_playback(self):
        self.clear_play_timers()

        if self.playing_index is not None:
            self.play_buttons[self.playing_index].setText("Play")

        self.playing_index = None

    def clear_play_timers(self):
        for timer in self.play_timers:
            timer.stop()

        self.play_timers.clear()

    def play_sounds(self, sound_names):
        for sound_name in sound_names:
            sound = self.sounds.get(sound_name)
            if sound:
                sound.play()

    def sounds_for_note(self, note):
        if note["duration"].endswith("r"):
            return []

        instrument = note.get("instrument", "")
        if instrument:
            sound_names = [name for name in ("kick", "snare", "ride") if name in instrument]
            if "hihat" in instrument:
                sound_names.append("stick")
            return sound_names

        return ["stick"]

    def get_time_signature(self, index):
        numerator_input, denominator_input = self.time_signature_inputs[index]
        numerator = int(numerator_input.text() or 4)
        denominator = int(denominator_input.text() or 4)

        if denominator not in {1, 2, 4, 8, 16}:
            denominator = 4
            denominator_input.setText("4")

        return numerator, denominator


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = RhythmApp()
    window.show()

    sys.exit(app.exec())
