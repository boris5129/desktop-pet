from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QFormLayout,
                               QLabel, QProgressBar, QSpinBox, QVBoxLayout)

from src.model import Settings


STYLE = """
QDialog { background: #fff8df; color: #412c20; }
QLabel, QCheckBox { color: #412c20; }
QProgressBar { background: #fffdf5; border: 1px solid #c9a96c;
               border-radius: 6px; text-align: center; color: #412c20; }
QProgressBar::chunk { background: #ffc940; border-radius: 5px; }
"""


class StatusWindow(QDialog):
    def __init__(self, image):
        super().__init__()
        self.setWindowTitle("피카츄 상태")
        self.setStyleSheet(STYLE)
        self.setMinimumWidth(290)
        layout = QVBoxLayout(self)
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setPixmap(QPixmap(str(image)).scaled(96, 96, Qt.AspectRatioMode.KeepAspectRatio))
        layout.addWidget(image_label)
        self.heading = QLabel()
        self.heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.heading.setStyleSheet("font-size: 19px; font-weight: bold")
        layout.addWidget(self.heading)
        form = QFormLayout()
        self.bars = {}
        for key, label in (("xp", "경험치"), ("fullness", "포만감"),
                           ("happiness", "행복도"), ("energy", "체력")):
            self.bars[key] = QProgressBar()
            form.addRow(label, self.bars[key])
        layout.addLayout(form)
        self.details = QLabel()
        layout.addWidget(self.details)

    def refresh(self, pet):
        self.heading.setText(f"{pet.name}  ·  레벨 {pet.level}")
        for key, bar in self.bars.items():
            bar.setRange(0, pet.target if key == "xp" else 100)
            bar.setValue(getattr(pet, key))
            bar.setFormat("%v / %m")
        created = datetime.fromisoformat(pet.created).astimezone().date()
        days = max(1, (datetime.now().date() - created).days + 1)
        self.details.setText(f"함께한 지 {days}일\n누적 상호작용 {pet.interactions}회\n현재 상태  {pet.state}")


class SettingsWindow(QDialog):
    def __init__(self, settings):
        super().__init__()
        self.setWindowTitle("피카츄 설정")
        self.setStyleSheet(STYLE)
        form = QFormLayout(self)
        self.controls = {}
        for key, label, low, high, suffix in (
            ("size", "캐릭터 크기 (모두)", 64, 240, " px"),
            ("speed", "이동 속도", 30, 240, " px/s"),
        ):
            control = QSpinBox()
            control.setRange(low, high)
            control.setSuffix(suffix)
            control.setValue(getattr(settings, key))
            self.controls[key] = control
            form.addRow(label, control)
        for key, label in (("roam", "자동 이동"), ("on_top", "항상 위에 표시"),
                           ("bubbles", "말풍선 표시"), ("sound", "효과음"),
                           ("startup", "Windows 시작 시 자동 실행"),
                           ("fullscreen", "전체 화면 프로그램 사용 시 숨기기")):
            control = QCheckBox(label)
            control.setChecked(getattr(settings, key))
            self.controls[key] = control
            form.addRow(control)
        buttons = QDialogButtonBox()
        buttons.addButton("저장", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton("취소", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self):
        return Settings(**{
            key: control.isChecked() if isinstance(control, QCheckBox) else control.value()
            for key, control in self.controls.items()
        })
