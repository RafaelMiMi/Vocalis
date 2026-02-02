import sys
import os
import logging
from PySide6.QtWidgets import (QApplication, QSystemTrayIcon, QMenu, QDialog, 
                               QVBoxLayout, QLabel, QComboBox, QDialogButtonBox, 
                               QFormLayout, QLineEdit, QCheckBox, QWidget, QProgressBar,
                               QTabWidget, QTextEdit, QListWidget, QPushButton, QHBoxLayout,
                               QMessageBox)
from PySide6.QtGui import QIcon, QAction, QPainter, QColor, QPen, QPixmap, QKeySequence
from PySide6.QtCore import Slot, QThread, Signal, Qt, QTimer, QPoint, QObject
from core.config import ConfigManager, AppConfig
from core.audio import AudioRecorder
from core.history import HistoryManager
from core.prompt_engine import PromptEngine
from app.hotkeys import get_manager
from app import output_actions
from core.ipc import IPCServer
import sounddevice as sd
import numpy as np

logger = logging.getLogger(__name__)

def create_placeholder_icon():
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor("transparent"))
    painter = QPainter(pixmap)
    painter.setBrush(QColor("#4A90E2"))
    painter.drawEllipse(2, 2, 60, 60)
    painter.setPen(QColor("white"))
    painter.drawText(20, 35, "V")
    painter.end()
    return QIcon(pixmap)

class VisualizerWindow(QWidget):
    stop_clicked = Signal()
    cancel_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.resize(300, 100)
        self.amplitude = 0.0
        self.message = "Listening..."
        self.mode = "recording" # recording or processing
        
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() // 2 - 150, screen.height() - 200)

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
        
        # Pill Background
        painter.setBrush(QColor(0, 0, 0, 180))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 25, 25)
        
        # Visualizer Wave (only animate if recording)
        painter.setPen(QPen(QColor("#4A90E2"), 3))
        center_y = self.height() // 2
        
        if self.mode == "recording":
            radius = 10 + (self.amplitude * 100)
            if radius > self.height()/2 - 10: radius = self.height()/2 - 10
        else:
            # Pulse animation could go here, but static circle for processing is fine
            radius = 15
            
        painter.setBrush(QColor("#4A90E2"))
        painter.drawEllipse(QPoint(self.width()//2, center_y), int(radius), int(radius))
        
        # Label
        painter.setPen(QColor("white"))
        painter.drawText(60, 0, 180, 100, Qt.AlignCenter, self.message)

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


class WorkerThread(QThread):
    finished = Signal(str)
    error = Signal(str)
    status_update = Signal(str)
    audio_amplitude = Signal(float)

    def __init__(self, config_manager, prompt_engine):
        super().__init__()
        self.config_manager = config_manager
        self.prompt_engine = prompt_engine
        self.recorder = None

    def run(self):
        try:
            config = self.config_manager.get()
            
            # Determine current mode settings
            mode_name = config.current_mode
            mode_data = config.modes.get(mode_name, config.modes["quick"])
            
            # 1. Record
            self.status_update.emit(f"Listening ({mode_name})...")
            self.recorder = AudioRecorder(device_index=config.input_device)
            
            def stream_callback(data):
                rms = np.sqrt(np.mean(data**2))
                self.audio_amplitude.emit(float(rms))

            path = self.recorder.record_once(max_duration=3600, stream_callback=stream_callback) # 1 hour max
            
            # 2. Transcribe
            self.status_update.emit("Transcribing...")
            from core.transcription import TranscriberFactory
            transcriber = TranscriberFactory.get_transcriber(config)
            text = transcriber.transcribe(path, language=(None if config.language == 'auto' else config.language))
            
            # 3. Apply Prompt (AI) using dict access since dynamic dict in config
            prompt_id = mode_data.get("prompt_id")
            if prompt_id:
                self.status_update.emit("AI Processing...")
                text = self.prompt_engine.process(text, prompt_id)

            # 4. Output
            output_action_type = mode_data.get("output_action", "clipboard")
            file_path = mode_data.get("file_path")
            
            output_actions.execute(output_action_type, text, file_path=file_path)
            
            os.unlink(path)
            self.finished.emit(text)
            
        except Exception as e:
            logger.error(f"Worker failed: {e}")
            self.error.emit(str(e))

    def stop_recording(self):
        if self.recorder:
            self.recorder.stop()

class HotkeyEdit(QLineEdit):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setReadOnly(True)
        self.setPlaceholderText("Click and press keys...")
        
    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        
        # If just a modifier is pressed, don't update yet (or show pending?)
        # But we want to show the full combo.
        
        # Check for clear command (Backspace used to clear)
        if key == Qt.Key_Backspace:
            self.clear()
            return
            
        parts = []
        if modifiers & Qt.ControlModifier:
            parts.append("<ctrl>")
        if modifiers & Qt.AltModifier:
            parts.append("<alt>")
        if modifiers & Qt.ShiftModifier:
            parts.append("<shift>")
        if modifiers & Qt.MetaModifier:
            parts.append("<super>")
            
        # Filter out modifier-only key events
        if key not in [Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta]:
            # Convert Qt key to reasonable string
            # QKeySequence return strings like "Space", "F1", "A"
            key_seq = QKeySequence(key).toString().lower()
            if key_seq == "space": parts.append("space") # pynput prefers lowercase
            elif key_seq: parts.append(key_seq)
            else:
                 # Fallback for some keys if empty
                 pass
                 
        if parts:
            if len(parts) == 1 and parts[0] in ["<ctrl>", "<alt>", "<shift>", "<super>"]:
                # Just modifier, maybe don't set text yet? Or show it?
                # showing it is better feedback
                pass
            self.setText("+".join(parts))



class SettingsDialog(QDialog):
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vocalis Settings")
        self.resize(500, 400)
        self.config_manager = config_manager
        self.config = config_manager.get()
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
        
        self.hotkey_edit = HotkeyEdit(self.config.hotkey)
        self.hotkey_edit.setToolTip("Click to record new hotkey (e.g., <ctrl>+<alt>+k)")
        general_layout.addRow("Global Hotkey:", self.hotkey_edit)

        # Autostart
        self.autostart_check = QCheckBox("Run on Startup")
        self.autostart_check.setChecked(self._check_autostart())
        self.autostart_check.toggled.connect(self._toggle_autostart)
        general_layout.addRow("", self.autostart_check)
        
        # Wayland Warning
        if os.environ.get("XDG_SESSION_TYPE") == "wayland":
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
        
        self.m_path_edit = QLineEdit()
        self.m_path_edit.setPlaceholderText("/path/to/file.md (optional)")
        editor_layout.addRow("File Path:", self.m_path_edit)

        btn_layout = QHBoxLayout()
        self.add_mode_btn = QPushButton("New")
        self.add_mode_btn.clicked.connect(self._new_mode)
        self.save_mode_btn = QPushButton("Save Mode")
        self.save_mode_btn.clicked.connect(self._save_mode)
        self.del_mode_btn = QPushButton("Delete")
        self.del_mode_btn.clicked.connect(self._delete_mode)
        
        btn_layout.addWidget(self.add_mode_btn)
        btn_layout.addWidget(self.save_mode_btn)
        btn_layout.addWidget(self.del_mode_btn)
        editor_layout.addRow(btn_layout)
        
        # Active Mode Selection
        modes_layout.addWidget(editor_widget, stretch=2)
        
        # Add a bottom row for "Default/Active Mode"
        main_layout_shim = QVBoxLayout()
        main_layout_shim.addLayout(modes_layout)
        
        active_layout = QHBoxLayout()
        active_layout.addWidget(QLabel("Active Mode:"))
        self.active_mode_combo = QComboBox()
        active_layout.addWidget(self.active_mode_combo)
        main_layout_shim.addLayout(active_layout)
        
        self.modes_tab.setLayout(main_layout_shim)
        
        self._refresh_prompt_combo()
        self._refresh_mode_list()
        
        self.tabs.addTab(self.modes_tab, "Modes")

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

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

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
        self.active_mode_combo.clear()
        
        for mid, mdata in self.config.modes.items():
            name = mdata.get("name") if isinstance(mdata, dict) else mdata.get("name", mid)
            self.mode_list.addItem(f"{name} ({mid})")
            self.active_mode_combo.addItem(name, mid)
            
        # Set active
        index = self.active_mode_combo.findData(self.config.current_mode)
        if index >= 0: self.active_mode_combo.setCurrentIndex(index)

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
        
        self.m_path_edit.setText(data.get("file_path") or "")

    def _new_mode(self):
        self.mode_list.clearSelection()
        self.m_id_edit.clear()
        self.m_id_edit.setReadOnly(False)
        self.m_name_edit.clear()
        self.m_path_edit.clear()
        self.m_prompt_combo.setCurrentIndex(0)
        self.m_action_combo.setCurrentIndex(0)

    def _save_mode(self):
        mid = self.m_id_edit.text().strip()
        if not mid: return
        
        new_data = {
            "name": self.m_name_edit.text(),
            "prompt_id": self.m_prompt_combo.currentData(),
            "output_action": self.m_action_combo.currentText(),
            "file_path": self.m_path_edit.text() or None
        }
        
        self.config.modes[mid] = new_data
        self._refresh_mode_list()
        
        items = self.mode_list.findItems(f"{new_data['name']} ({mid})", Qt.MatchExactly)
        if items:
            self.mode_list.setCurrentItem(items[0])

    def _delete_mode(self):
        mid = self.m_id_edit.text().strip()
        if mid in self.config.modes:
            del self.config.modes[mid]
            self._new_mode()
            self._refresh_mode_list()

    def accept(self):
        self.config.input_device = self.device_combo.currentData()
        self.config.hotkey = self.hotkey_edit.text()
        
        self.config.transcription_provider = self.provider_combo.currentText()
        self.config.api_key = self.api_key_edit.text()
        self.config.remote_model_name = self.remote_model_edit.text()
        self.config.model_preset = self.preset_combo.currentText()
        
        self.config.current_mode = self.active_mode_combo.currentData()
        # Prompts/Modes are modified in-place
        self.config_manager.save()
        super().accept()

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

class SystemTrayApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        
        self.config_manager = ConfigManager()
        self.history_manager = HistoryManager()
        self.prompt_engine = PromptEngine(self.config_manager)
        
        self.hotkey_manager = get_manager(self.start_listening, self.config_manager.get().hotkey)
        
        self.tray_icon = QSystemTrayIcon()
        self.tray_icon.setIcon(create_placeholder_icon())
        self.tray_icon.setToolTip("Vocalis")
        
        self.worker = None
        self.visualizer = None 

        self.command_signals = CommandSignals()
        self.command_signals.trigger.connect(self.start_listening)
        
        self.ipc = IPCServer(self.command_signals.trigger.emit)
        self.ipc.start()

        self.setup_menu()
        self.tray_icon.show()

        # Start Hotkeys
        try:
            self.hotkey_manager.start()
        except NotImplementedError:
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
        config = self.config_manager.get()
        config.current_mode = mode_key
        self.config_manager.save()
        self._refresh_mode_menu()

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
        if self.worker and self.worker.isRunning():
            self.status_action.setText("Stopping...")
            self.listen_action.setEnabled(False)
            self.worker.stop_recording()
            return

        logger.info("Starting listening flow...")
        self.status_action.setText("Starting...") 
        self.listen_action.setText("Stop Listening")
        
        if not self.visualizer:
            self.visualizer = VisualizerWindow()
            # Connect stop/cancel buttons
            self.visualizer.stop_clicked.connect(self.start_listening)
            self.visualizer.cancel_clicked.connect(self.cancel_processing)
        
        self.worker = WorkerThread(self.config_manager, self.prompt_engine)
        self.worker.finished.connect(self.on_transcription_finished)
        self.worker.error.connect(self.on_error)
        self.worker.status_update.connect(self.on_status_update) 
        self.worker.audio_amplitude.connect(self.visualizer.update_audio)
        self.worker.start()

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
        self.status_action.setText(status)
        if "Listening" in status:
            self.listen_action.setEnabled(True)
            self.listen_action.setText("Stop Listening")
            self.visualizer.set_status(status, mode="recording")
            self.visualizer.show()
        else:
            self.listen_action.setEnabled(False) 
            self.listen_action.setText("Processing...")
            self.visualizer.set_status(status, mode="processing")
            self.visualizer.show()

    def on_transcription_finished(self, text):
        logger.info(f"Finished: {text}")
        self.status_action.setText("Ready")
        self.listen_action.setText("Start Listening")
        self.listen_action.setEnabled(True)
        if self.visualizer: self.visualizer.hide()
        
        # Add to history
        self.history_manager.add(text, self.config_manager.get().current_mode)
        
        self.tray_icon.showMessage("Vocalis", "Transcription Complete", QSystemTrayIcon.Information, 1000)
        
        # Open Editor (Only if text exists)
        if text:
            editor = ResultEditor(text)
            editor.exec()

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
