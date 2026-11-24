import json
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QVBoxLayout)


DEFAULT_ID = "pokemon:pikachu"
SPRITE_ROOT = "https://play.pokemonshowdown.com/sprites/"


@dataclass(frozen=True)
class Character:
    key: str
    name: str
    english: str
    sprite: str
    skill: str
    effect: str

    @property
    def category(self):
        return self.key.split(":")[0]

    @property
    def filename(self):
        return self.key.split(":")[1] + Path(self.sprite).suffix

    @property
    def url(self):
        return SPRITE_ROOT + self.sprite


def load_catalog(assets):
    entries = (Character(*row) for row in json.loads((assets / "roster.json").read_bytes()))
    return {entry.key: entry for entry in entries}


class Picker(QDialog):
    def __init__(self, catalog, selected, owned):
        super().__init__()
        self.catalog = catalog
        self.owned = owned
        self.selected = set(selected).intersection(owned)
        self.setWindowTitle("돌볼 친구 선택")
        self.resize(480, 590)
        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("한글 또는 영문 이름 검색")
        layout.addWidget(self.search)
        self.category = QComboBox()
        for title, value in (("보유", "owned"), ("전체", ""), ("포켓몬", "pokemon"), ("디지몬", "digimon"),
                             ("선택됨", "selected")):
            self.category.addItem(title, value)
        layout.addWidget(self.category)
        self.list = QListWidget()
        layout.addWidget(self.list)
        self.count = QLabel()
        layout.addWidget(self.count)
        buttons = QDialogButtonBox()
        buttons.addButton("적용", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton("취소", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.search.textChanged.connect(self.refresh)
        self.category.currentIndexChanged.connect(self.refresh)
        self.list.itemChanged.connect(self.toggle)
        self.refresh()

    def refresh(self):
        query = self.search.text().strip().casefold()
        category = self.category.currentData()
        self.list.clear()
        self.list.blockSignals(True)
        try:
            for entry in self.catalog.values():
                if category == "selected" and entry.key not in self.selected:
                    continue
                unlocked = entry.key in self.owned
                if category == "owned" and not unlocked:
                    continue
                if category not in ("", "selected", "owned", entry.category):
                    continue
                if query not in f"{entry.name} {entry.english} {entry.key.split(':')[1]}".casefold():
                    continue
                label = "포켓몬" if entry.category == "pokemon" else "디지몬"
                level = self.owned.get(entry.key, 0)
                badge = f" · 강화 +{level}" if level else ""
                if not unlocked:
                    badge = " · 잠김"
                item = QListWidgetItem(f"{entry.name}  ·  {label}  ·  {entry.skill}{badge}")
                item.setData(Qt.ItemDataRole.UserRole, entry.key)
                if unlocked:
                    item.setCheckState(Qt.CheckState.Checked if entry.key in self.selected
                                       else Qt.CheckState.Unchecked)
                self.list.addItem(item)
        finally:
            self.list.blockSignals(False)
        self.update_count()

    def toggle(self, item):
        key = item.data(Qt.ItemDataRole.UserRole)
        if key not in self.owned:
            return
        if item.checkState() == Qt.CheckState.Checked:
            self.selected.add(key)
        else:
            self.selected.discard(key)
        self.update_count()

    def update_count(self):
        self.count.setText(f"{len(self.selected)}마리 선택 · 처음 받는 스프라이트는 인터넷 연결 필요")
