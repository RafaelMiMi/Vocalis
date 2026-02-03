import sys
import os
import math
import logging
from PySide6.QtWidgets import (QApplication, QSystemTrayIcon, QMenu, QDialog, 
                               QVBoxLayout, QLabel, QComboBox, QDialogButtonBox, 
                               QFormLayout, QLineEdit, QCheckBox, QWidget, QProgressBar,
                               QTabWidget, QTextEdit, QListWidget, QPushButton, QHBoxLayout,
                               QMessageBox, QDoubleSpinBox)
from PySide6.QtGui import (QIcon, QAction, QPainter, QColor, QPen, QPainterPath, 
                         QKeySequence, QFont, QPixmap)
from PySide6.QtCore import Slot, QThread, Signal, Qt, QTimer, QPoint, QObject
from core.config import ConfigManager, AppConfig
from core.audio import AudioRecorder
from core.history import HistoryManager
from core.transcription import TranscriberFactory
from core.prompt_engine import PromptEngine
from core.processing import TextProcessor
from core.dictionary import DictionaryManager
from core.snippets import SnippetManager
from core.profiles import ProfileManager
from app.hotkeys import get_manager
from app import output_actions
from core.ipc import IPCServer
from core.sounds import SoundManager
import sounddevice as sd
import numpy as np

logger = logging.getLogger(__name__)

def create_placeholder_icon(color="#4A90E2"):
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor("transparent"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    # Circle
    painter.setBrush(QColor(color))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(2, 2, 60, 60)
    
    # "V" Text
    painter.setPen(QColor("white"))
    font = painter.font()
    font.setPixelSize(40)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(0, 0, 64, 64, Qt.AlignCenter, "V")
    
    painter.end()
    return QIcon(pixmap)

class VisualizerWindow(QWidget):
    stop_clicked = Signal()
    cancel_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.resize(300, 100)
        self.amplitude = 0.0
        self.message = "Listening..."
        self.mode = "recording" # recording or processing
        
        screen = QApplication.primaryScreen().geometry()
        # Center horizontally, but place at bottom (minus padding)
        x = screen.x() + (screen.width() - 300) // 2
        y = screen.y() + (screen.height() - 150)
        self.move(x, y)

        # Action Button (Stop/Cancel)
        self.action_btn = QPushButton("Stop", self)
        self.action_btn.setCursor(Qt.PointingHandCursor)
        self.update_button_style("rec_stop") # Initial style
        self.action_btn.clicked.connect(self.on_btn_click)
        self.action_btn.resize(60, 24)
        self.action_btn.move(220, 38)

    def update_button_style(self, style_type):
        if style_type == "rec_stop":
            color = "rgba(231, 76, 60, 200)" # Red
            hover = "rgba(192, 57, 43, 255)"
            text = "Stop"
        elif style_type == "cancel":
            color = "rgba(149, 165, 166, 200)" # Grey/Orange
            hover = "rgba(127, 140, 141, 255)"
            text = "Cancel"
        else:
            return
            
        self.action_btn.setText(text)
        self.action_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 12px;
                padding: 4px 10px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {hover};
            }}
        """)

    def on_btn_click(self):
        logger.info(f"Visualizer button clicked. Mode: {self.mode}")
        if self.mode == "recording":
            self.stop_clicked.emit()
        else:
            self.cancel_clicked.emit()

    def set_status(self, message, mode="recording"):
        self.message = message
        self.mode = mode
        if mode == "recording":
            self.update_button_style("rec_stop")
            self.action_btn.show()
        elif mode == "processing":
            self.update_button_style("cancel")
            self.action_btn.show()
        else:
            self.action_btn.hide()
        self.update()

    def update_audio(self, amplitude):
        self.amplitude = amplitude
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Pill Background (Translucent Black)
        painter.setBrush(QColor(0, 0, 0, 180))
        painter.setPen(Qt.NoPen)
        rect = self.rect()
        painter.drawRoundedRect(rect, 25, 25)
        
        # Wave Animation
        center_y = self.height() // 2
        width = self.width()
        
        if self.mode == "recording":
            # Dynamic Wave
            # Use current time to phase shift the sine wave
            import time
            current_time = time.time() * 10
            
            path = QPainterPath()
            path.moveTo(0, center_y)
            
            # Amplitude Scaling
            # self.amplitude is roughly 0.0 to 1.0 (though can be higher)
            # We want max height to be ~40px
            amp_scale = min(self.amplitude * 200, 40) 
            if amp_scale < 2: amp_scale = 2 # Minimum movement
            
            # Draw Sine Wave
            for x in range(0, width, 5):
                norm_x = x / width
                window = 4 * norm_x * (1 - norm_x) # 0->1->0
                y_offset = math.sin((x * 0.1) + current_time) * amp_scale * window
                path.lineTo(x, center_y + y_offset)
            
            painter.setPen(QPen(QColor("#4A90E2"), 3))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)
            
        elif self.mode == "processing":
            # Spinner / Pulse
            import time
            t = time.time() * 5
            radius = 10 + math.sin(t) * 3
            painter.setBrush(QColor("#4A90E2"))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPoint(int(width/2), center_y), int(radius), int(radius))
        
        painter.setPen(QColor("white"))
        painter.drawText(rect, Qt.AlignCenter, self.message)
        super().paintEvent(event) # Just in case

        super().paintEvent(event) # Just in case
class ResultEditor(QDialog):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vocalis Result")
        self.resize(500, 300)
        self.setup_ui(text)
        
        # Center near top of screen or mouse
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width()//2 - 250, screen.height()//2 - 150)

    def setup_ui(self, text):
        layout = QVBoxLayout(self)
        
        self.text_edit = QTextEdit(text)
        layout.addWidget(self.text_edit)
        
        btn_layout = QHBoxLayout()
        
        copy_btn = QPushButton("Copy && Close")
        copy_btn.clicked.connect(self.copy_and_close)
        btn_layout.addWidget(copy_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)

    def copy_and_close(self):
        output_actions.execute("clipboard", self.text_edit.toPlainText())
        self.accept()


from core.processing import TextProcessor

logger = logging.getLogger(__name__)

class WorkerThread(QThread):
    finished = Signal(str, dict)
    error = Signal(str)
    status_update = Signal(str)
    audio_amplitude = Signal(float) # Keep this for visualizer if needed elsewhere, though recording is moved

    def __init__(self, config_manager, prompt_engine, text_processor):
        super().__init__()
        self.config_manager = config_manager
        self.prompt_engine = prompt_engine
        self.text_processor = text_processor
        self.recorder = None
        self._should_stop_recording = False # Flag for thread movement

    def run(self):
        try:
            config = self.config_manager.get()
            
            # Determine current mode settings
            mode_name = config.current_mode
            mode_data = config.modes.get(mode_name, config.modes["quick"])
            
            # 1. Record
            self.status_update.emit(f"Listening ({mode_name})...")
            
            # Helper to emit amplitude
            def stream_callback(data):
                rms = np.sqrt(np.mean(data**2))
                # logger.debug(f"RMS: {rms}") 
                self.audio_amplitude.emit(float(rms))
            
            # Initialize Recorder HERE (Background Thread)
            logger.info("Initializing AudioRecorder...")
            from core.audio import AudioRecorder
            self.recorder = AudioRecorder(device_index=config.input_device)
            
            # Check if stop was pressed during init
            if self._should_stop_recording:
                logger.info("Stop flag set during init, aborting.")
                self.recorder.stop() # Ensure it knows it's stopped
                self.finished.emit("", mode_data)
                return

            logger.info("Starting record_once...")
            # We need to act on self._should_stop_recording if it flips AFTER we start recording but BEFORE we enter the loop?
            # record_once blocks. We rely on stop_recording() calling self.recorder.stop() from the MAIN thread.
            # But there is a race: if stop_recording is called while we are in AudioRecorder.__init__ or just before record_once.
            
            # Since record_once is blocking, the other thread calls recorder.stop(). 
            # We just need to ensure self.recorder is reachable. It is assigned above.
            
            path = self.recorder.record_once(max_duration=3600, stream_callback=stream_callback)
            logger.info(f"record_once returned: {path}")
            
            if not path or not os.path.exists(path):
                self.finished.emit("", mode_data)
                return

            # 2. Transcribe
            self.status_update.emit("Transcribing...")
            from core.transcription import TranscriberFactory
            transcriber = TranscriberFactory.get_transcriber(config)
            text = transcriber.transcribe(path, language=(None if config.language == 'auto' else config.language))
            
            # 3. Process (AI + Dictionary + Snippets)
            self.status_update.emit("Processing text...")
            # Ensure mode_data is dict
            if hasattr(mode_data, "name"): mode_data = asdict(mode_data)
                
            final_text = self.text_processor.process(text, mode_data)
                
            if os.path.exists(path):
                os.unlink(path)

            # 4. Finish
            self.finished.emit(final_text, mode_data)
            
        except Exception as e:
            logger.error(f"Worker failed: {e}")
            self.error.emit(str(e))

    def stop_recording(self):
        logger.info("WorkerThread stop_recording called")
        self._should_stop_recording = True
        if self.recorder:
            logger.info("Calling recorder.stop()")
            self.recorder.stop()
        else:
            logger.warning("Recorder not yet ready, set flag.")

class HotkeyEdit(QLineEdit):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setReadOnly(True)
        self.setPlaceholderText("Click and press keys...")
        
    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        
        if key == Qt.Key_Backspace or key == Qt.Key_Delete:
            self.clear()
            self.setText("")
            return

        # Ignore standalone modifiers (Pressing just Ctrl shouldn't set the hotkey yet)
        if key in [Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta]:
            return

        # Build string
        parts = []
        if modifiers & Qt.MetaModifier: parts.append("<super>")
        if modifiers & Qt.ControlModifier: parts.append("<ctrl>")
        if modifiers & Qt.AltModifier: parts.append("<alt>")
        if modifiers & Qt.ShiftModifier: parts.append("<shift>")
        
        # Get Key Name
        key_seq = QKeySequence(key).toString()
        if key_seq:
            parts.append(key_seq.lower())
            
        if parts:
            final_key = "+".join(parts)
            self.setText(final_key)



class SettingsDialog(QDialog):
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vocalis Settings")
        self.resize(500, 400)
        self.config_manager = config_manager
        self.config = config_manager.get()
        self.profile_manager = ProfileManager(config_manager)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Tab 1: General
        self.general_tab = QWidget()
        general_layout = QFormLayout(self.general_tab)
        
        # Microphones
        self.device_combo = QComboBox()
        self._populate_devices()
        general_layout.addRow("Microphone:", self.device_combo)
        
        # Current Mode Selector
        self.mode_selector = QComboBox()
        # Populate with modes
        for mid, mdata in self.config.modes.items():
            name = mdata.get("name") if isinstance(mdata, dict) else mdata.name
            self.mode_selector.addItem(name, mid)
        # Set current
        idx = self.mode_selector.findData(self.config.current_mode)
        if idx >= 0:
            self.mode_selector.setCurrentIndex(idx)
        
        self.mode_selector.currentIndexChanged.connect(self._on_settings_mode_changed)
        general_layout.addRow("Active Mode:", self.mode_selector)

        self.hotkey_edit = QLineEdit(self.config.hotkey)
        self.hotkey_edit.setPlaceholderText("Click to set (e.g. <Super>space)")
        self.hotkey_edit.setReadOnly(True) # Capture key presses
        self.hotkey_edit.installEventFilter(self) # We need to implement eventFilter
        
        general_layout.addRow("Global Hotkey:", self.hotkey_edit)

        # Paste Delay
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0.1, 5.0)
        self.delay_spin.setSingleStep(0.1)
        self.delay_spin.setValue(self.config.paste_delay)
        self.delay_spin.setSuffix(" sec")
        self.delay_spin.setToolTip("Delay before pasting to ensure headers/focus are correct.")
        general_layout.addRow("Paste Delay:", self.delay_spin)

        # Autostart
        self.autostart_check = QCheckBox("Run on Startup")
        self.autostart_check.setChecked(self._check_autostart())
        self.autostart_check.toggled.connect(self._toggle_autostart)
        general_layout.addRow("", self.autostart_check)

        # Show Visualizer
        self.visualizer_check = QCheckBox("Show Visualizer Window")
        self.visualizer_check.setChecked(self.config.show_visualizer)
        general_layout.addRow("", self.visualizer_check)

        # Clipboard Privacy
        self.allow_clipboard_check = QCheckBox("Allow AI to read Clipboard")
        self.allow_clipboard_check.setChecked(getattr(self.config, "allow_clipboard_access", True))
        self.allow_clipboard_check.setToolTip("Enables {clipboard} placeholder in prompts.")
        general_layout.addRow("", self.allow_clipboard_check)
        
        # Wayland Warning (Linux only)
        if sys.platform == "linux" and os.environ.get("XDG_SESSION_TYPE") == "wayland":
            warning = QLabel("Wayland detected: App cannot capture global hotkeys.\nPlease set a system shortcut to run: <b>vocalis --listen</b>")
            warning.setWordWrap(True)
            warning.setStyleSheet("color: orange; font-size: 11px;")
            general_layout.addRow("", warning)
        
        self.tabs.addTab(self.general_tab, "General")

        # Tab 2: Models
        self.model_tab = QWidget()
        model_layout = QFormLayout(self.model_tab)
        
        # Provider
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["local", "openai", "groq"])
        self.provider_combo.setCurrentText(self.config.transcription_provider)
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        model_layout.addRow("Provider:", self.provider_combo)
        
        # API Key (Hidden for local)
        self.api_key_label = QLabel("API Key:")
        self.api_key_edit = QLineEdit(self.config.api_key or "")
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        model_layout.addRow(self.api_key_label, self.api_key_edit)
        
        # Remote Model Name (Hidden for local)
        self.remote_model_label = QLabel("Remote Model:")
        self.remote_model_edit = QLineEdit(self.config.remote_model_name)
        model_layout.addRow(self.remote_model_label, self.remote_model_edit)

        # Local Preset (Hidden for remote)
        self.preset_label = QLabel("Quality Preset:")
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["fast", "balanced", "high_quality"])
        self.preset_combo.setCurrentText(self.config.model_preset)
        model_layout.addRow(self.preset_label, self.preset_combo)
        
        self._on_provider_changed(self.config.transcription_provider)
        
        self.tabs.addTab(self.model_tab, "Models")

        # Tab 3: Modes
        self.modes_tab = QWidget()
        modes_layout = QHBoxLayout(self.modes_tab)
        
        # Left: List of Modes
        self.mode_list = QListWidget()
        self.mode_list.currentRowChanged.connect(self._on_mode_selected)
        modes_layout.addWidget(self.mode_list, stretch=1)
        
        # Right: Editor
        editor_widget = QWidget()
        editor_layout = QFormLayout(editor_widget)
        
        self.m_id_edit = QLineEdit()
        self.m_id_edit.setPlaceholderText("unique_id")
        editor_layout.addRow("ID:", self.m_id_edit)
        
        self.m_name_edit = QLineEdit()
        editor_layout.addRow("Name:", self.m_name_edit)
        
        self.m_prompt_combo = QComboBox()
        self.m_prompt_combo.addItem("None", None)
        # Populate prompts later
        editor_layout.addRow("Prompt:", self.m_prompt_combo)
        
        self.m_action_combo = QComboBox()
        self.m_action_combo.addItems(["clipboard", "paste", "file"])
        editor_layout.addRow("Action:", self.m_action_combo)
        
        self.m_paste_method = QComboBox()
        self.m_paste_method.addItems(["auto", "ctrl_v", "type", "copy_only"])
        self.m_paste_method.setToolTip("Auto: Tries best method. Ctrl+V: Standard paste. Type: Types characters. Copy Only: No output.")
        editor_layout.addRow("Paste Method:", self.m_paste_method)
        
        self.m_path_edit = QLineEdit()
        self.m_path_edit.setPlaceholderText("/path/to/file.md (optional)")
        editor_layout.addRow("File Path:", self.m_path_edit)

        btn_layout = QHBoxLayout()
        self.set_active_btn = QPushButton("Set as Active")
        self.set_active_btn.clicked.connect(self._set_active_from_list)
        self.set_active_btn.setStyleSheet("background-color: #4A90E2; color: white; font-weight: bold;")
        
        self.add_mode_btn = QPushButton("New")
        self.add_mode_btn.clicked.connect(self._new_mode)
        self.save_mode_btn = QPushButton("Save Mode")
        self.save_mode_btn.clicked.connect(self._save_mode)
        self.del_mode_btn = QPushButton("Delete")
        self.del_mode_btn.clicked.connect(self._delete_mode)
        
        btn_layout.addWidget(self.set_active_btn)
        btn_layout.addWidget(self.add_mode_btn)
        btn_layout.addWidget(self.save_mode_btn)
        btn_layout.addWidget(self.del_mode_btn)
        editor_layout.addRow(btn_layout)
        
        modes_layout.addWidget(editor_widget, stretch=2)
        
        self.modes_tab.setLayout(modes_layout)
        
        self._refresh_mode_list()
        self._refresh_prompt_combo()
        
        self.tabs.addTab(self.modes_tab, "Manage Modes")

        # Tab 4: Prompts
        self.prompts_tab = QWidget()
        prompts_layout = QHBoxLayout(self.prompts_tab)
        
        # Left: List of Prompts
        self.prompt_list = QListWidget()
        self.prompt_list.currentRowChanged.connect(self._on_prompt_selected)
        prompts_layout.addWidget(self.prompt_list, stretch=1)
        
        # Right: Editor
        editor_widget = QWidget()
        editor_layout = QFormLayout(editor_widget)
        
        self.p_id_edit = QLineEdit()
        self.p_id_edit.setPlaceholderText("unique_id")
        editor_layout.addRow("ID:", self.p_id_edit)
        
        self.p_name_edit = QLineEdit()
        editor_layout.addRow("Name:", self.p_name_edit)
        
        self.p_desc_edit = QLineEdit()
        editor_layout.addRow("Description:", self.p_desc_edit)
        
        self.p_system_edit = QTextEdit()
        self.p_system_edit.setPlaceholderText("You are a helpful assistant...")
        self.p_system_edit.setFixedHeight(60)
        editor_layout.addRow("System Prompt:", self.p_system_edit)

        self.p_template_edit = QTextEdit()
        self.p_template_edit.setPlaceholderText("{text}")
        self.p_template_edit.setFixedHeight(60)
        editor_layout.addRow("User Template:", self.p_template_edit)
        
        btn_layout = QHBoxLayout()
        self.add_prompt_btn = QPushButton("New")
        self.add_prompt_btn.clicked.connect(self._new_prompt)
        self.save_prompt_btn = QPushButton("Save Prompt")
        self.save_prompt_btn.clicked.connect(self._save_prompt)
        self.del_prompt_btn = QPushButton("Delete")
        self.del_prompt_btn.clicked.connect(self._delete_prompt)
        
        btn_layout.addWidget(self.add_prompt_btn)
        btn_layout.addWidget(self.save_prompt_btn)
        btn_layout.addWidget(self.del_prompt_btn)
        editor_layout.addRow(btn_layout)
        
        prompts_layout.addWidget(editor_widget, stretch=2)
        
        self._refresh_prompt_list()
        self.tabs.addTab(self.prompts_tab, "Prompts")

        # Tab 5: Dictionary
        self.dict_tab = QWidget()
        dict_layout = QHBoxLayout(self.dict_tab)
        
        # Left: List
        self.dict_list = QListWidget()
        self.dict_list.currentRowChanged.connect(self._on_dict_selected)
        dict_layout.addWidget(self.dict_list, stretch=1)
        
        # Right: Editor
        editor_widget = QWidget()
        editor_layout = QFormLayout(editor_widget)
        
        self.d_spoken_edit = QLineEdit()
        self.d_spoken_edit.setPlaceholderText("Spoken phrase")
        editor_layout.addRow("Spoken:", self.d_spoken_edit)
        
        self.d_written_edit = QLineEdit()
        self.d_written_edit.setPlaceholderText("Replacement text")
        editor_layout.addRow("Written:", self.d_written_edit)
        
        btn_layout = QHBoxLayout()
        self.add_dict_btn = QPushButton("New")
        self.add_dict_btn.clicked.connect(self._new_dict_entry)
        self.save_dict_btn = QPushButton("Save")
        self.save_dict_btn.clicked.connect(self._save_dict_entry)
        self.del_dict_btn = QPushButton("Delete")
        self.del_dict_btn.clicked.connect(self._delete_dict_entry)
        
        btn_layout.addWidget(self.add_dict_btn)
        btn_layout.addWidget(self.save_dict_btn)
        btn_layout.addWidget(self.del_dict_btn)
        editor_layout.addRow(btn_layout)
        
        dict_layout.addWidget(editor_widget, stretch=2)
        
        self._refresh_dict_list()
        self.tabs.addTab(self.dict_tab, "Dictionary")

        # Tab 6: Snippets
        self.snip_tab = QWidget()
        snip_layout = QHBoxLayout(self.snip_tab)
        
        # Left: List
        self.snip_list = QListWidget()
        self.snip_list.currentRowChanged.connect(self._on_snip_selected)
        snip_layout.addWidget(self.snip_list, stretch=1)
        
        # Right: Editor
        editor_widget = QWidget()
        editor_layout = QFormLayout(editor_widget)
        
        self.s_trigger_edit = QLineEdit()
        self.s_trigger_edit.setPlaceholderText("Trigger phrase")
        editor_layout.addRow("Trigger:", self.s_trigger_edit)
        
        self.s_replace_edit = QTextEdit() # Multi-line snippet
        self.s_replace_edit.setPlaceholderText("Expanded text.\nSupports {date}, {time}")
        editor_layout.addRow("Expansion:", self.s_replace_edit)
        
        btn_layout = QHBoxLayout()
        self.add_snip_btn = QPushButton("New")
        self.add_snip_btn.clicked.connect(self._new_snip_entry)
        self.save_snip_btn = QPushButton("Save")
        self.save_snip_btn.clicked.connect(self._save_snip_entry)
        self.del_snip_btn = QPushButton("Delete")
        self.del_snip_btn.clicked.connect(self._delete_snip_entry)
        
        btn_layout.addWidget(self.add_snip_btn)
        btn_layout.addWidget(self.save_snip_btn)
        btn_layout.addWidget(self.del_snip_btn)
        editor_layout.addRow(btn_layout)
        
        snip_layout.addWidget(editor_widget, stretch=2)
        
        self._refresh_snip_list()
        self.tabs.addTab(self.snip_tab, "Snippets")

        # Tab 6: Profiles
        self.profiles_tab = QWidget()
        prof_layout = QHBoxLayout(self.profiles_tab)
        
        self.prof_list = QListWidget()
        self.prof_list.currentRowChanged.connect(self._on_prof_selected)
        prof_layout.addWidget(self.prof_list, stretch=1)
        
        prof_editor = QWidget()
        prof_edit_layout = QFormLayout(prof_editor)
        
        self.p_rule_edit = QLineEdit()
        self.p_rule_edit.setPlaceholderText("Window Title (e.g., 'Firefox')")
        prof_edit_layout.addRow("App/Title:", self.p_rule_edit)

        # Help Label
        help_lbl = QLabel("If detection fails (e.g. Wayland), bind a system shortcut to:\n'vocalis --mode <ModeName>'")
        help_lbl.setStyleSheet("color: gray; font-style: italic; font-size: 10px;")
        prof_edit_layout.addRow("", help_lbl)
        
        self.p_mode_combo = QComboBox()
        # Populate with modes
        for mid, mdata in self.config.modes.items():
            name = mdata.get("name") if isinstance(mdata, dict) else mdata.name
            self.p_mode_combo.addItem(name, mid)
        prof_edit_layout.addRow("Target Mode:", self.p_mode_combo)
        
        prof_btns = QHBoxLayout()
        add_prof_btn = QPushButton("Save Rule")
        add_prof_btn.clicked.connect(self._save_prof_entry)
        new_prof_btn = QPushButton("New")
        new_prof_btn.clicked.connect(self._new_prof_entry)
        del_prof_btn = QPushButton("Delete")
        del_prof_btn.clicked.connect(self._delete_prof_entry)
        
        prof_btns.addWidget(new_prof_btn)
        prof_btns.addWidget(add_prof_btn)
        prof_btns.addWidget(del_prof_btn)
        prof_edit_layout.addRow(prof_btns)
        
        test_btn = QPushButton("Test Detection (Wait 3s)")
        test_btn.clicked.connect(self._test_detection)
        prof_edit_layout.addRow("", test_btn)
        
        prof_layout.addWidget(prof_editor, stretch=1)
        
        self.tabs.addTab(self.profiles_tab, "Profiles")
        self._refresh_prof_list()

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_settings_mode_changed(self, index):
        if index < 0: return
        mode_id = self.mode_selector.itemData(index)
        if mode_id:
            logger.info(f"Settings: Selected mode {mode_id}")
            self.config.current_mode = mode_id
            # We don't save immediately, only on OK? 
            # Actually, user expects instant switch usually depending on UX.
            # But SettingsDialog pattern usually implies "Save on OK".
            # However, for "Current Mode" it might be state vs config.
            # Let's keep it in config object, saved on accept().

    def _on_provider_changed(self, text):
        is_local = (text == "local")
        self.api_key_label.setVisible(not is_local)
        self.api_key_edit.setVisible(not is_local)
        self.remote_model_label.setVisible(not is_local)
        self.remote_model_edit.setVisible(not is_local)
        self.preset_label.setVisible(is_local)
        self.preset_combo.setVisible(is_local)
        
        if text == "openai":
            self.remote_model_edit.setPlaceholderText("whisper-1")
        elif text == "groq":
             self.remote_model_edit.setPlaceholderText("distil-whisper-large-v3-en")

    def _populate_devices(self):
        devices = sd.query_devices()
        self.device_combo.addItem("Default", userData=None)
        current_idx = 0
        for idx, dev in enumerate(devices):
            if dev['max_input_channels'] > 0:
                name = f"{idx}: {dev['name']}"
                self.device_combo.addItem(name, userData=idx)
                if self.config.input_device == idx:
                    current_idx = self.device_combo.count() - 1
        
        if self.config.input_device is not None:
             self.device_combo.setCurrentIndex(current_idx)

    def _refresh_prompt_list(self):
        self.prompt_list.clear()
        for pid, pdata in self.config.prompts.items():
            # Handle dict/obj differences
            name = pdata.get("name") if isinstance(pdata, dict) else pdata.name
            self.prompt_list.addItem(f"{name} ({pid})")

    def _on_prompt_selected(self, row):
        if row < 0: return
        item_text = self.prompt_list.item(row).text()
        pid = item_text.split(" (")[-1].rstrip(")")
        
        data = self.config.prompts.get(pid)
        if not data: return
        
        is_dict = isinstance(data, dict)
        self.p_id_edit.setText(pid)
        self.p_id_edit.setReadOnly(True) # Cannot change ID of existing
        self.p_name_edit.setText(data.get("name") if is_dict else data.name)
        self.p_desc_edit.setText(data.get("description") if is_dict else data.description)
        self.p_system_edit.setPlainText(data.get("system_prompt", "") if is_dict else getattr(data, "system_prompt", ""))
        self.p_template_edit.setPlainText(data.get("template", "") if is_dict else data.template)

    def _new_prompt(self):
        self.prompt_list.clearSelection()
        self.p_id_edit.clear()
        self.p_id_edit.setReadOnly(False)
        self.p_name_edit.clear()
        self.p_desc_edit.clear()
        self.p_system_edit.clear()
        self.p_template_edit.setText("{text}")

    def _save_prompt(self):
        pid = self.p_id_edit.text().strip()
        if not pid: return
        
        new_data = {
            "id": pid,
            "name": self.p_name_edit.text(),
            "description": self.p_desc_edit.text(),
            "system_prompt": self.p_system_edit.toPlainText(),
            "template": self.p_template_edit.toPlainText()
        }
        
        self.config.prompts[pid] = new_data
        self._refresh_prompt_list()
        # Reselect
        items = self.prompt_list.findItems(f"{new_data['name']} ({pid})", Qt.MatchExactly)
        if items:
            self.prompt_list.setCurrentItem(items[0])

    def _delete_prompt(self):
        pid = self.p_id_edit.text().strip()
        if pid in self.config.prompts:
            del self.config.prompts[pid]
            self._new_prompt()
            self._refresh_prompt_list()

    def _refresh_prompt_combo(self):
        self.m_prompt_combo.clear()
        self.m_prompt_combo.addItem("None", None)
        for pid, pdata in self.config.prompts.items():
            name = pdata.get("name") if isinstance(pdata, dict) else pdata.name
            self.m_prompt_combo.addItem(f"{name}", pid)

    def _refresh_mode_list(self):
        self.mode_list.clear()
        
        # We also need to refresh the combo on the General tab
        current_data = self.mode_selector.currentData()
        self.mode_selector.clear()
        
        for mid, mdata in self.config.modes.items():
            name = mdata.get("name") if isinstance(mdata, dict) else mdata.get("name", mid)
            self.mode_list.addItem(f"{name} ({mid})")
            self.mode_selector.addItem(name, mid)
            
        # Restore selection or set to config default
        target = current_data if current_data else self.config.current_mode
        
        found_idx = -1
        for i in range(self.mode_selector.count()):
            if str(self.mode_selector.itemData(i)) == str(target):
                 found_idx = i
                 break
        
        if found_idx >= 0:
            self.mode_selector.setCurrentIndex(found_idx)
        else:
            # Fallback to defaults
            if self.mode_selector.count() > 0:
                self.mode_selector.setCurrentIndex(0)

    def _on_mode_selected(self, row):
        if row < 0: return
        item_text = self.mode_list.item(row).text()
        mid = item_text.split(" (")[-1].rstrip(")")
        
        data = self.config.modes.get(mid)
        if not data: return
        
        self.m_id_edit.setText(mid)
        self.m_id_edit.setReadOnly(True)
        self.m_name_edit.setText(data.get("name", ""))
        
        prompt_id = data.get("prompt_id")
        index = self.m_prompt_combo.findData(prompt_id)
        self.m_prompt_combo.setCurrentIndex(index if index >= 0 else 0)
        
        action = data.get("output_action", "clipboard")
        index = self.m_action_combo.findText(action)
        self.m_action_combo.setCurrentIndex(index if index >= 0 else 0)
        
        paste_method = data.get("paste_method", "auto")
        index = self.m_paste_method.findText(paste_method)
        self.m_paste_method.setCurrentIndex(index if index >= 0 else 0)
        
        self.m_path_edit.setText(data.get("file_path") or "")

    def _new_mode(self):
        self.mode_list.clearSelection()
        self.m_id_edit.clear()
        self.m_id_edit.setReadOnly(False)
        self.m_name_edit.clear()
        self.m_path_edit.clear()
        self.m_prompt_combo.setCurrentIndex(0)
        self.m_action_combo.setCurrentIndex(0)
        self.m_paste_method.setCurrentIndex(0) # Auto

    def _save_mode(self):
        mid = self.m_id_edit.text().strip()
        if not mid: return
        
        new_data = {
            "name": self.m_name_edit.text(),
            "prompt_id": self.m_prompt_combo.currentData(),
            "output_action": self.m_action_combo.currentText(),
            "paste_method": self.m_paste_method.currentText(),
            "file_path": self.m_path_edit.text() or None
        }
        
        self.config.modes[mid] = new_data
        self._refresh_mode_list()
        
        items = self.mode_list.findItems(f"{new_data['name']} ({mid})", Qt.MatchExactly)
        if items:
            self.mode_list.setCurrentItem(items[0])

    def _set_active_from_list(self):
        mid = self.m_id_edit.text().strip()
        if not mid or mid not in self.config.modes:
            return
            
        index = self.mode_selector.findData(mid)
        if index >= 0:
            self.mode_selector.setCurrentIndex(index)
            QMessageBox.information(self, "Mode Set", f"Active mode set to: {self.config.modes[mid].get('name', mid)}")

    def _delete_mode(self):
        mid = self.m_id_edit.text().strip()
        if mid in self.config.modes:
            del self.config.modes[mid]
            self._new_mode()
            self._refresh_mode_list()

    def accept(self):
        # ... (Previous accept logic, make sure to add dict/snp saving if needed? No, logic is in-place)
        # But wait, config.modes is managed in-place? 
        # Yes, existing logic for modes/prompts modifies self.config.modes/prompts directly.
        # Dictionary/Snippets should do the same.
        
        # We need to capture changes if we only modified self.config.dictionary/snippets
        # But wait, self.config is the object from ConfigManager?
        # Yes. AppConfig object.
        # So modifications are already in memory.
        
        self.config.input_device = self.device_combo.currentData()
        self.config.hotkey = self.hotkey_edit.text()
        
        self.config.transcription_provider = self.provider_combo.currentText()
        self.config.api_key = self.api_key_edit.text()
        self.config.remote_model_name = self.remote_model_edit.text()
        self.config.model_preset = self.preset_combo.currentText()
        self.config.show_visualizer = self.visualizer_check.isChecked()
        self.config.allow_clipboard_access = self.allow_clipboard_check.isChecked()
        self.config.paste_delay = self.delay_spin.value()
        
        new_mode = self.mode_selector.currentData()
        logger.info(f"Settings calling accept. Selected mode: {new_mode}")
        
        self.config.current_mode = new_mode
        # Prompts/Modes/Dict/Snip are modified in-place
        self.config_manager.save()
        
        # Verify save
        logger.info(f"Config saved. Current mode in config: {self.config_manager.get().current_mode}")
        
        super().accept()
        
    # --- Dictionary Helpers ---
    def _refresh_dict_list(self):
        self.dict_list.clear()
        for spoken, written in self.config.dictionary.items():
            self.dict_list.addItem(f"{spoken} -> {written}")

    def _on_dict_selected(self, row):
        if row < 0: return
        item_text = self.dict_list.item(row).text()
        spoken, written = item_text.split(" -> ", 1)
        self.d_spoken_edit.setText(spoken)
        self.d_written_edit.setText(written)

    def _new_dict_entry(self):
        self.dict_list.clearSelection()
        self.d_spoken_edit.clear()
        self.d_written_edit.clear()
        self.d_spoken_edit.setFocus()

    def _save_dict_entry(self):
        spoken = self.d_spoken_edit.text().strip()
        written = self.d_written_edit.text().strip()
        if not spoken: return
        
        self.config.dictionary[spoken] = written
        self._refresh_dict_list()
        self._new_dict_entry()

    def _delete_dict_entry(self):
        spoken = self.d_spoken_edit.text().strip()
        if spoken in self.config.dictionary:
            del self.config.dictionary[spoken]
            self._refresh_dict_list()
            self._new_dict_entry()

    # --- Snippet Helpers ---
    def _refresh_snip_list(self):
        self.snip_list.clear()
        for trigger, replacement in self.config.snippets.items():
            short_rep = (replacement[:20] + '..') if len(replacement) > 20 else replacement
            self.snip_list.addItem(f"{trigger} -> {short_rep}")

    def _on_snip_selected(self, row):
        if row < 0: return
        item_text = self.snip_list.item(row).text()
        trigger = item_text.split(" -> ", 1)[0]
        
        if trigger in self.config.snippets:
            self.s_trigger_edit.setText(trigger)
            self.s_replace_edit.setPlainText(self.config.snippets[trigger])

    def _new_snip_entry(self):
        self.snip_list.clearSelection()
        self.s_trigger_edit.clear()
        self.s_replace_edit.clear()
        self.s_trigger_edit.setFocus()

    def _save_snip_entry(self):
        trigger = self.s_trigger_edit.text().strip()
        replacement = self.s_replace_edit.toPlainText() # allow newlines
        if not trigger: return
        
        self.config.snippets[trigger] = replacement
        self._refresh_snip_list()
        self._new_snip_entry()

    def _delete_snip_entry(self):
        trigger = self.s_trigger_edit.text().strip()
        if trigger in self.config.snippets:
            del self.config.snippets[trigger]
            self._refresh_snip_list()
            self._new_snip_entry()

    # --- Profile Helpers ---
    def _refresh_prof_list(self):
        self.prof_list.clear()
        for rule, mode_id in self.config.app_profiles.items():
            mode_name = mode_id
            if mode_id in self.config.modes:
                mdata = self.config.modes[mode_id]
                mode_name = mdata.get("name") if isinstance(mdata, dict) else mdata.name
            self.prof_list.addItem(f"{rule} -> {mode_name}")

    def _on_prof_selected(self, row):
        if row < 0: return
        item_text = self.prof_list.item(row).text()
        rule = item_text.split(" -> ", 1)[0]
        
        if rule in self.config.app_profiles:
            self.p_rule_edit.setText(rule)
            mode_id = self.config.app_profiles[rule]
            idx = self.p_mode_combo.findData(mode_id)
            if idx >= 0:
                self.p_mode_combo.setCurrentIndex(idx)

    def _new_prof_entry(self):
        self.prof_list.clearSelection()
        self.p_rule_edit.clear()
        self.p_rule_edit.setFocus()

    def _save_prof_entry(self):
        rule = self.p_rule_edit.text().strip()
        mode_id = self.p_mode_combo.currentData()
        if not rule or not mode_id: return
        
        self.config.app_profiles[rule] = mode_id
        self._refresh_prof_list()
        self._new_prof_entry()

    def _delete_prof_entry(self):
        rule = self.p_rule_edit.text().strip()
        if rule in self.config.app_profiles:
            del self.config.app_profiles[rule]
            self._refresh_prof_list()
            self._new_prof_entry()

    def _test_detection(self):
        # Delay 3 seconds to let user switch valid window
        QTimer.singleShot(3000, self._perform_test_detection)
        
    def _perform_test_detection(self):
        try:
            detected = self.profile_manager.detect_active_app()
            QMessageBox.information(self, "Detection Result", f"Detected App Identifier:\n'{detected}'")
        except Exception as e:
            QMessageBox.warning(self, "Detection Failed", f"Error: {e}")

    def _check_autostart(self):
        autostart_dir = os.path.expanduser("~/.config/autostart")
        desktop_file = os.path.join(autostart_dir, "vocalis.desktop")
        return os.path.exists(desktop_file)

    def _toggle_autostart(self, checked):
        autostart_dir = os.path.expanduser("~/.config/autostart")
        if not os.path.exists(autostart_dir):
            os.makedirs(autostart_dir)
            
        target = os.path.join(autostart_dir, "vocalis.desktop")
        
        if checked:
            content = """[Desktop Entry]
Type=Application
Name=Vocalis
Comment=Voice Assistant
Exec=vocalis --gui
Icon=vocalis
Terminal=false
Categories=Utility;
"""
            try:
                with open(target, "w") as f:
                    f.write(content)
            except Exception as e:
                logger.error(f"Failed to enable autostart: {e}")
                QMessageBox.warning(self, "Error", f"Could not enable autostart: {e}")
                self.autostart_check.setChecked(False)
        else:
            if os.path.exists(target):
                os.remove(target)

class CommandSignals(QObject):
    trigger = Signal()
    set_mode = Signal(str)

class SystemTrayApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        
        # On macOS, if we want a Dock icon, we shouldn't act purely as a tray app, 
        # or we need to ensure the policy is set correctly.
        # However, typically PySide6 apps show in dock by default unless code explicitly hides it.
        # The issue described "nothing in tray" -> maybe icon transparency issue?
        # But "can't see in dock" -> strange for a normal QApplication.
        
        # Force Dock Icon (Policy) if needed
        if sys.platform == 'darwin':
             self.app.setApplicationName("Vocalis")
             # This policy ensures it appears in Dock
             self.app.setApplicationDisplayName("Vocalis")

        self.config_manager = ConfigManager()
        self.history_manager = HistoryManager()
        self.prompt_engine = PromptEngine(self.config_manager)
        self.text_processor = TextProcessor(self.config_manager, self.prompt_engine)
        self.profile_manager = ProfileManager(self.config_manager)
        
        # Initialize Audio Manager for Sounds
        from core.sounds import SoundManager
        self.sound_manager = SoundManager()
        
        self.hotkey_manager = get_manager(self.start_listening, self.config_manager.get().hotkey)
        
        self.tray_icon = QSystemTrayIcon(self.app)
        
        # Set Icon
        # Use a programmatic icon if file not found
        icon_path = os.path.join(os.path.dirname(__file__), "../resources/icon.png")
        if os.path.exists(icon_path):
             self.tray_icon.setIcon(QIcon(icon_path))
             self.app.setWindowIcon(QIcon(icon_path))
        else:
             self.tray_icon.setIcon(create_placeholder_icon())
             self.app.setWindowIcon(create_placeholder_icon())
        
        self.tray_icon.setVisible(True)
        self.tray_icon.setToolTip("Vocalis")
        
        self.worker = None
        self.visualizer = None 

        self.command_signals = CommandSignals()
        self.command_signals.trigger.connect(self.start_listening)
        self.command_signals.set_mode.connect(self.set_mode)
        
        self.sound_manager = SoundManager()
        
        self.ipc = IPCServer(self.handle_ipc_command)
        self.ipc.start()

        self.setup_menu()
        self.tray_icon.show()

        # Start Hotkeys
        try:
            self.hotkey_manager.start()
        except NotImplementedError:
            pass

    def handle_ipc_command(self, command):
        if command == "TOGGLE":
            self.command_signals.trigger.emit()
        elif command.startswith("SET_MODE:"):
            try:
                mode_id = command.split(":", 1)[1]
                self.command_signals.set_mode.emit(mode_id)
            except IndexError:
                pass

    def setup_menu(self):
        self.menu = QMenu()
        
        # Status
        self.status_action = QAction("Ready", self.app)
        self.status_action.setEnabled(False)
        self.menu.addAction(self.status_action)
        self.menu.addSeparator()

        # Main Action
        self.listen_action = QAction("Start Listening", self.app)
        self.listen_action.triggered.connect(self.start_listening)
        self.menu.addAction(self.listen_action)
        
        # Mode Selection Submenu
        self.mode_menu = self.menu.addMenu("Mode")
        self.mode_action_group = None # Can be managed if needed
        self._refresh_mode_menu()

        # History Submenu
        self.history_menu = self.menu.addMenu("History")
        self.history_actions = []
        self.menu.aboutToShow.connect(self._refresh_history_menu) # Refresh on open

        self.menu.addSeparator()
        
        # Settings & Quit
        self.settings_action = QAction("Settings...", self.app)
        self.settings_action.triggered.connect(self.open_settings)
        self.menu.addAction(self.settings_action)
        
        self.quit_action = QAction("Quit", self.app)
        self.quit_action.triggered.connect(self.quit_app)
        self.menu.addAction(self.quit_action)
        
        self.tray_icon.setContextMenu(self.menu)

    def _refresh_mode_menu(self):
        self.mode_menu.clear()
        config = self.config_manager.get()
        for mode_key, mode_data in config.modes.items():
            action = QAction(mode_data.get("name", mode_key), self.app)
            action.setCheckable(True)
            action.setChecked(mode_key == config.current_mode)
            # Use default argument capture for lambda
            action.triggered.connect(lambda checked=False, k=mode_key: self.set_mode(k))
            self.mode_menu.addAction(action)

    def set_mode(self, mode_key):
        logger.info(f"Switching to mode: {mode_key}")
        try:
            config = self.config_manager.get()
            config.current_mode = mode_key
            self.config_manager.save()
            self._refresh_mode_menu()
            
            # Show a tooltip/message to confirm
            self.tray_icon.showMessage("Vocalis", f"Switched to {mode_key} mode", QSystemTrayIcon.Information, 1000)
        except Exception as e:
            logger.error(f"Failed to set mode: {e}")

    def _refresh_history_menu(self):
        self.history_menu.clear()
        items = self.history_manager.get_recent()
        if not items:
            no_hist = QAction("No history", self.app)
            no_hist.setEnabled(False)
            self.history_menu.addAction(no_hist)
            return

        for item in items[:5]: # Show top 5
            label = f"{item.text[:20]}..."
            action = QAction(label, self.app)
            action.triggered.connect(lambda checked=False, t=item.text: self._copy_history(t))
            self.history_menu.addAction(action)

    def _copy_history(self, text):
        output_actions.execute("clipboard", text)
        self.tray_icon.showMessage("Vocalis", "Copied from history!", QSystemTrayIcon.Information, 1000)

    def start_listening(self):
        logger.info(f"start_listening called. Worker: {self.worker}, IsRunning: {self.worker.isRunning() if self.worker else 'None'}")
        if self.worker and self.worker.isRunning():
            self.status_action.setText("Stopping...")
            self.listen_action.setEnabled(False)
            self.worker.stop_recording()
            return

        logger.info("Starting listening flow...")
        
        # --- Auto-Switch Profile ---
        try:
            active_app = self.profile_manager.detect_active_app() # e.g. "Vocalis - VS Code"
            logger.info(f"Detected Active App: {active_app}")
            
            target_mode = self.profile_manager.get_profile(active_app)
            if target_mode and target_mode != self.config_manager.get().current_mode:
                logger.info(f"Auto-switching to mode: {target_mode}")
                self.set_mode(target_mode)
        except Exception as e:
            logger.warning(f"Profile switch failed: {e}")
        # ---------------------------

        self.sound_manager.play_start()
        self.status_action.setText("Starting...") 
        self.listen_action.setText("Stop Listening")
        
        if not self.visualizer:
            self.visualizer = VisualizerWindow()
            # Connect stop/cancel buttons
            self.visualizer.stop_clicked.connect(self.start_listening)
            self.visualizer.cancel_clicked.connect(self.cancel_processing)
            
        if self.visualizer.isVisible():
             # Already visible? Maybe implied stop?
             pass
        else:
             self.visualizer.show()
        
        # Start Worker
        self.worker = WorkerThread(self.config_manager, self.prompt_engine, self.text_processor)
        self.worker.status_update.connect(self.visualizer.set_status)
        self.worker.finished.connect(self.on_transcription_finished)
        self.worker.error.connect(self.on_error)
        self.worker.status_update.connect(self.on_status_update) 
        self.worker.audio_amplitude.connect(self.visualizer.update_audio)
        self.worker.start()

    # start_processing removed as it is merged back into worker

    def cancel_processing(self):
        logger.warning("User cancelled processing.")
        if self.worker and self.worker.isRunning():
            self.worker.terminate() # Force kill for now
            self.worker.wait()
            
        self.status_action.setText("Ready (Cancelled)")
        self.listen_action.setEnabled(True)
        self.listen_action.setText("Start Listening")
        if self.visualizer: self.visualizer.hide()
        self.tray_icon.showMessage("Vocalis", "Operation Cancelled", QSystemTrayIcon.Information, 1000)

    def on_status_update(self, status):
        config = self.config_manager.get()
        self.status_action.setText(status)
        
        if "Listening" in status:
            self.listen_action.setEnabled(True)
            self.listen_action.setText("Stop Listening")
            
            # Red Icon for Recording
            self.tray_icon.setIcon(create_placeholder_icon("#E74C3C")) # Red
            
            if config.show_visualizer:
                self.visualizer.set_status(status, mode="recording")
                self.visualizer.show()
            else:
                self.visualizer.hide() # Ensure hidden if previously shown
                
        elif "Transcribing" in status or "Processing" in status:
            if "Transcribing" in status: self.sound_manager.play_stop() # Play stop sound when recording ends
            self.listen_action.setEnabled(False) 
            self.listen_action.setText("Processing...")
            
            # Orange Icon for Processing
            self.tray_icon.setIcon(create_placeholder_icon("#F39C12")) # Orange
            
            if config.show_visualizer:
                self.visualizer.set_status(status, mode="processing")
                self.visualizer.show()
            else:
                self.visualizer.hide()
        else:
            # Reset to Blue (Ready)
            self.tray_icon.setIcon(create_placeholder_icon("#4A90E2"))
            self.visualizer.hide()

    def on_transcription_finished(self, text, mode_data):
        logger.info(f"Finished: {text}")
        if text: self.sound_manager.play_success()
        
        # Reset UI
        self.status_action.setText("Ready")
        self.tray_icon.setIcon(create_placeholder_icon("#4A90E2")) # Reset to Blue
        self.listen_action.setText("Start Listening")
        self.listen_action.setEnabled(True)
        if self.visualizer: self.visualizer.hide()
        # Force process events to ensure window is gone
        QApplication.processEvents()
        
        # Add to history
        self.history_manager.add(text, self.config_manager.get().current_mode)
        
        self.tray_icon.showMessage("Vocalis", "Transcription Complete", QSystemTrayIcon.Information, 1000)
        
        # Delay output slightly to ensure focus is restored to target app
        # 500ms should be safer for Wayland/Window switching
        # Delay output slightly to ensure focus is restored to target app
        # 500ms should be safer for Wayland/Window switching
        delay_ms = int(self.config_manager.get().paste_delay * 1000)
        QTimer.singleShot(delay_ms, lambda: self._perform_output(text, mode_data))

    def _perform_output(self, text, mode_data):
        output_action_type = mode_data.get("output_action", "clipboard")
        file_path = mode_data.get("file_path")
        output_actions.execute(output_action_type, text, file_path=file_path)
        
        # Open Editor (Only if text exists and explicitly requested - disabled for seamless flow)
        # if text:
        #     editor = ResultEditor(text)
        #     editor.exec()

    def on_error(self, err):
        logger.error(err)
        self.status_action.setText("Error")
        self.listen_action.setText("Start Listening")
        self.listen_action.setEnabled(True)
        if self.visualizer: self.visualizer.hide()
        
        # Modal Error Dialog
        QMessageBox.critical(None, "Vocalis Error", f"An error occurred:\n{err}")

    def open_settings(self):
        dialog = SettingsDialog(self.config_manager)
        if dialog.exec():
            self.hotkey_manager.update_hotkey(self.config_manager.get().hotkey)
            self._refresh_mode_menu()

    def quit_app(self):
        if hasattr(self, 'ipc') and self.ipc:
            self.ipc.stop()
        self.hotkey_manager.stop()
        if self.visualizer: self.visualizer.close()
        self.app.quit()

    def run(self):
        sys.exit(self.app.exec())

def run_ui():
    app_instance = SystemTrayApp()
    app_instance.run()
