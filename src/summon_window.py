import logging

from PySide6.QtCore import QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from src.economy import DRAW_COST, DUPLICATE_REFUND, STAGE_ODDS
from src.summon_stage import SummonStage


class SummonWindow(QDialog):
    def __init__(self, flock):
        super().__init__()
        self.flock = flock
        self.economy = flock.economy
        self.pending = None
        self.reply = None
        self.image_unavailable = False
        self.setWindowTitle("친구 뽑기")
        self.resize(460, 470)
        self.setStyleSheet(
            "QDialog { background: #f5f0e5; } QLabel { color: #252a39; }"
            "QPushButton { padding: 8px 12px; }")
        layout = QVBoxLayout(self)
        self.balance = QLabel()
        self.balance.setStyleSheet("font-size: 19px; font-weight: bold;")
        layout.addWidget(self.balance)
        tiers = ("미진화", "1단계", "2단계", "3단계 이상")
        odds = "   ·   ".join(f"{tier} {chance}%" for tier, chance in zip(tiers, STAGE_ODDS))
        layout.addWidget(QLabel(odds))
        info = QLabel(f"중복은 {DUPLICATE_REFUND}골드 환급과 강화 +1을 받습니다.")
        info.setWordWrap(True)
        layout.addWidget(info)
        self.stage = SummonStage()
        self.stage.animation.finished.connect(self.reveal)
        layout.addWidget(self.stage)
        self.result = QLabel("배틀타워에서 승리하면 골드를 얻을 수 있어요.")
        self.result.setWordWrap(True)
        self.result.setMinimumHeight(55)
        layout.addWidget(self.result)
        buttons = QDialogButtonBox()
        self.buy = buttons.addButton(f"1회 뽑기 · {DRAW_COST}골드", QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton("친구 선택…", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton("닫기", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.buy.clicked.connect(self.pull)
        layout.addWidget(buttons)
        self.refresh()

    def refresh(self):
        self.balance.setText(f"{self.economy.gold:,} 골드  ·  보유 {len(self.economy.owned)}마리")
        self.buy.setEnabled(self.pending is None and self.economy.gold >= DRAW_COST)

    def pull(self):
        if self.pending is not None:
            return
        try:
            result = self.economy.draw()
        except OSError:
            logging.exception("뽑기 저장 실패")
            self.result.setText("저장하지 못했어요. 골드는 차감되지 않았습니다.")
            return
        except ValueError as error:
            self.result.setText(str(error))
            return
        self.abort_image()
        self.image_unavailable = False
        self.pending = result
        entry = self.flock.catalog[result.key]
        path = self.flock.sprite_path(entry)
        if not path.is_file():
            path = self.flock.portraits.get(entry.key)
        image = QPixmap(str(path)) if path else QPixmap()
        self.result.setText("친구가 나타나는 중…")
        self.stage.begin(entry.category, image)
        self.refresh()
        if image.isNull():
            request = QNetworkRequest(QUrl(entry.url))
            request.setTransferTimeout(9000)
            self.reply = self.flock.network.get(request)
            self.reply.finished.connect(lambda reply=self.reply: self.image_ready(entry, reply))

    def reveal(self):
        result, self.pending = self.pending, None
        if result is None:
            return
        name = self.flock.catalog[result.key].name
        if result.duplicate:
            self.result.setText(f"{name} 강화 +{result.upgrades} · {result.refund}골드 환급")
        else:
            self.result.setText(f"새 친구 {name} 획득! 친구 선택에서 바탕화면에 불러올 수 있어요.")
        if self.image_unavailable:
            self.result.setText(self.result.text() + "\n이미지는 인터넷 연결 후 다시 받을 수 있어요.")
        self.refresh()

    def image_ready(self, entry, reply):
        try:
            if self.reply is not reply:
                return
            self.reply = None
            if reply.error() != QNetworkReply.NetworkError.NoError:
                raise OSError(reply.errorString())
            path = self.flock.cache_sprite(entry, bytes(reply.readAll()))
            image = QPixmap(str(path))
            if image.isNull():
                raise OSError("이미지를 표시할 수 없습니다.")
            self.stage.set_image(image)
        except OSError:
            self.image_unavailable = True
            if self.pending is None:
                self.result.setText(self.result.text() + "\n이미지는 인터넷 연결 후 다시 받을 수 있어요.")
        finally:
            reply.deleteLater()

    def abort_image(self):
        reply, self.reply = self.reply, None
        if reply is not None:
            reply.abort()

    def done(self, result):
        self.stage.animation.stop()
        self.abort_image()
        super().done(result)
