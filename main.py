import json
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QLineEdit, QWidget, QHBoxLayout, QVBoxLayout, QPushButton
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWebEngineWidgets import QWebEngineView

from patterns import generate_pattern, preset_names


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
        self.resize(600, 840)
        self.setFixedSize(600, 840)

        self.web_views = []
        self.time_signature_inputs = []
        self.preset_inputs = []
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
            row_layout.setContentsMargins(0, 0, 0, 0)

            web = QWebEngineView()
            web.setFixedHeight(130)

            pattern_label = QLabel(f"Pattern {pattern_number + 1}")
            pattern_label.setFixedWidth(150)

            button = QPushButton("Generate")
            button.setFixedWidth(150)
            button.clicked.connect(
                lambda checked=False, index=pattern_number: self.generate(index)
            )

            play_button = QPushButton("Play")
            play_button.setFixedWidth(150)
            play_button.clicked.connect(
                lambda checked=False, index=pattern_number: self.play(index)
            )

            numerator_input = QLineEdit("2")
            numerator_input.setValidator(QIntValidator(1, 16))
            numerator_input.setFixedWidth(42)

            denominator_input = QLineEdit("4")
            denominator_input.setValidator(QIntValidator(1, 16))
            denominator_input.setFixedWidth(42)

            preset_input = QComboBox()
            preset_input.addItems(preset_names())
            preset_input.setFixedWidth(150)

            time_signature_layout = QHBoxLayout()
            time_signature_layout.setContentsMargins(0, 0, 0, 0)
            time_signature_layout.setSpacing(4)
            time_signature_layout.addWidget(numerator_input)
            time_signature_layout.addWidget(QLabel("/"))
            time_signature_layout.addWidget(denominator_input)
            time_signature_layout.addStretch()

            controls = QWidget()
            controls.setFixedWidth(150)
            controls_layout = QVBoxLayout()
            controls_layout.setContentsMargins(0, 0, 0, 0)
            controls_layout.addWidget(pattern_label)
            controls_layout.addWidget(preset_input)
            controls_layout.addLayout(time_signature_layout)
            controls_layout.addWidget(play_button)
            controls_layout.addWidget(button)
            controls_layout.addStretch()
            controls.setLayout(controls_layout)

            self.web_views.append(web)
            self.time_signature_inputs.append((numerator_input, denominator_input))
            self.preset_inputs.append(preset_input)
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
        preset_name = self.preset_inputs[index].currentText()
        pattern = generate_pattern(numerator, denominator, preset_name)
        self.current_patterns[index] = pattern
        html = make_html(pattern, numerator, denominator)
        self.web_views[index].setHtml(html)

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
            return [name for name in ("kick", "snare", "ride") if name in instrument]

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
