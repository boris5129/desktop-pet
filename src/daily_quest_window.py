from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QProgressBar, QVBoxLayout

from src.economy import DAILY_QUESTS


class DailyQuestWindow(QDialog):
    def __init__(self, economy):
        super().__init__()
        self.economy = economy
        self.setWindowTitle("일일 퀘스트")
        self.resize(410, 310)
        layout = QVBoxLayout(self)
        self.balance = QLabel()
        self.balance.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(self.balance)
        description = QLabel("직접 돌보면 진행도가 오르고, 완료 보상은 자동 지급돼요.\nPC 시간 기준 자정에 새 퀘스트가 열려요.")
        description.setWordWrap(True)
        layout.addWidget(description)
        self.rows = {}
        for action, (_, target, _) in DAILY_QUESTS.items():
            label = QLabel()
            bar = QProgressBar()
            bar.setRange(0, target)
            bar.setFormat("%v / %m")
            layout.addWidget(label)
            layout.addWidget(bar)
            self.rows[action] = label, bar
        buttons = QDialogButtonBox()
        buttons.addButton("닫기", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        timer = QTimer(self, interval=15000)
        timer.timeout.connect(self.refresh)
        timer.start()
        self.refresh()

    def refresh(self):
        self.balance.setText(f"보유 골드 {self.economy.gold:,}")
        counts = self.economy.daily_counts()
        for action, (label, bar) in self.rows.items():
            title, target, reward = DAILY_QUESTS[action]
            count = counts.get(action, 0)
            suffix = " · 지급 완료" if count == target else ""
            label.setText(f"{title} {target}회 · {reward}골드{suffix}")
            bar.setValue(count)
