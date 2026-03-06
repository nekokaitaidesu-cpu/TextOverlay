import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTextEdit, QPushButton, QFontComboBox, QSpinBox,
    QCheckBox, QColorDialog, QGroupBox, QFrame
)
from PyQt6.QtCore import Qt, QPoint, QRect, QObject, QEvent
from PyQt6.QtGui import QFont, QColor, QPainter, QPen

MARGIN = 12       # ハンドル用の余白（コンテンツの外側）
HANDLE_R = 6      # ハンドル円の半径
HANDLE_HIT = 12   # ハンドルのヒット判定半径


class OverlayWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(120, 60)
        self.setMouseTracking(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(MARGIN + 8, MARGIN + 4, MARGIN + 8, MARGIN + 4)

        self.label = QLabel("テキストをここに表示")
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.label)

        self.bg_enabled = True
        self.bg_color = QColor(0, 0, 0, 180)
        self.text_color = QColor(255, 255, 255)
        self._selected = False
        self._drag_pos = None
        self._last_gpos = None
        self._resize_dir = None
        self._drag_geom = None

        self._update_label_style()
        self.resize(420, 100)
        self.move(200, 200)

    # ── 座標計算 ──────────────────────────────
    def _content_rect(self):
        return QRect(MARGIN, MARGIN, self.width() - 2 * MARGIN, self.height() - 2 * MARGIN)

    def _handle_positions(self):
        cr = self._content_rect()
        x0, y0 = cr.left(), cr.top()
        x1, y1 = cr.right(), cr.bottom()
        mx, my = (x0 + x1) // 2, (y0 + y1) // 2
        return {
            "tl": QPoint(x0, y0), "t": QPoint(mx, y0), "tr": QPoint(x1, y0),
            "l":  QPoint(x0, my),                       "r":  QPoint(x1, my),
            "bl": QPoint(x0, y1), "b": QPoint(mx, y1), "br": QPoint(x1, y1),
        }

    def _hit_handle(self, pos):
        if not self._selected:
            return None
        for name, hpos in self._handle_positions().items():
            dx = pos.x() - hpos.x()
            dy = pos.y() - hpos.y()
            if dx * dx + dy * dy <= HANDLE_HIT * HANDLE_HIT:
                return name
        return None

    # ── 描画 ──────────────────────────────────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # ウィンドウ全体をほぼ透明で塗る → マージン部分もマウスイベントを受け取れるようにする
        painter.fillRect(self.rect(), QColor(0, 0, 0, 1))

        cr = self._content_rect()

        # 背景色（QPainter で直接描画 → stylesheet より確実に反映される）
        if self.bg_enabled:
            painter.fillRect(cr, self.bg_color)

        if self._selected:
            # 破線ボーダー
            pen = QPen(QColor(60, 130, 220), 1.5, Qt.PenStyle.DashLine)
            pen.setDashPattern([4, 3])
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(cr.adjusted(0, 0, -1, -1))

            # 8つのハンドル（白丸＋青枠）
            handle_pen = QPen(QColor(60, 130, 220), 1.5)
            for hpos in self._handle_positions().values():
                painter.setPen(handle_pen)
                painter.setBrush(QColor(255, 255, 255))
                painter.drawEllipse(hpos, HANDLE_R, HANDLE_R)

        painter.end()

    def _update_label_style(self):
        tc = f"rgb({self.text_color.red()},{self.text_color.green()},{self.text_color.blue()})"
        self.label.setStyleSheet(f"QLabel {{ color: {tc}; background-color: transparent; }}")

    # ── 外部API ───────────────────────────────
    def set_selected(self, selected):
        self._selected = selected
        self.update()
        if not selected:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def set_text(self, text):
        self.label.setText(text)

    def set_font(self, font):
        self.label.setFont(font)

    def set_text_color(self, color):
        self.text_color = color
        self._update_label_style()

    def set_bg_color(self, color):
        self.bg_color = color
        self.update()

    def set_bg_enabled(self, enabled):
        self.bg_enabled = enabled
        self.update()

    # ── マウス操作 ────────────────────────────
    def _cursor_for(self, direction):
        table = {
            "tl": Qt.CursorShape.SizeFDiagCursor, "br": Qt.CursorShape.SizeFDiagCursor,
            "tr": Qt.CursorShape.SizeBDiagCursor, "bl": Qt.CursorShape.SizeBDiagCursor,
            "l":  Qt.CursorShape.SizeHorCursor,   "r":  Qt.CursorShape.SizeHorCursor,
            "t":  Qt.CursorShape.SizeVerCursor,    "b":  Qt.CursorShape.SizeVerCursor,
        }
        return table.get(direction, Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()

        handle = self._hit_handle(pos)
        if handle:
            self._resize_dir = handle
            self._drag_pos = event.globalPosition().toPoint()
            self._last_gpos = event.globalPosition().toPoint()
            self._drag_geom = self.geometry()
            return

        if self._content_rect().contains(pos):
            self.set_selected(True)
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._resize_dir = None
        else:
            self.set_selected(False)
            self._drag_pos = None

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        gpos = event.globalPosition().toPoint()

        if self._drag_pos is None:
            # カーソル更新のみ
            handle = self._hit_handle(pos)
            if handle:
                self.setCursor(self._cursor_for(handle))
            elif self._content_rect().contains(pos):
                self.setCursor(Qt.CursorShape.SizeAllCursor if self._selected else Qt.CursorShape.ArrowCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            return

        if self._resize_dir:
            dx = gpos.x() - self._last_gpos.x()
            dy = gpos.y() - self._last_gpos.y()
            self._last_gpos = gpos
            x, y, w, h = self.x(), self.y(), self.width(), self.height()
            d = self._resize_dir
            min_w = 120
            min_h = 60
            if "r" in d:
                w = max(min_w, w + dx)
            if "b" in d:
                h = max(min_h, h + dy)
            if "l" in d:
                nw = max(min_w, w - dx)
                x = x + (w - nw)
                w = nw
            if "t" in d:
                nh = max(min_h, h - dy)
                y = y + (h - nh)
                h = nh
            self.move(x, y)
            self.resize(w, h)
        else:
            self.move(gpos - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self._resize_dir = None


class GlobalClickFilter(QObject):
    """オーバーレイ外クリックで選択解除"""
    def __init__(self, overlay):
        super().__init__()
        self.overlay = overlay

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress and self.overlay._selected:
            # obj が overlay またはその子でなければ解除
            w = obj
            is_overlay = False
            while w is not None:
                if w is self.overlay:
                    is_overlay = True
                    break
                w = w.parent() if callable(getattr(w, "parent", None)) else None
            if not is_overlay:
                self.overlay.set_selected(False)
        return False


class ControlPanel(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("テキストオーバーレイ - コントロール")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        self.overlay = OverlayWindow()
        self.overlay.show()

        self._click_filter = GlobalClickFilter(self.overlay)
        QApplication.instance().installEventFilter(self._click_filter)

        self._text_color = QColor(255, 255, 255)
        self._bg_color = QColor(0, 0, 0, 180)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 12)

        # テキスト入力
        text_group = QGroupBox("表示テキスト")
        tg_layout = QVBoxLayout(text_group)
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("ここにテキストを入力してください...")
        self.text_edit.setMaximumHeight(100)
        self.text_edit.textChanged.connect(self._on_text_changed)
        tg_layout.addWidget(self.text_edit)
        root.addWidget(text_group)

        # フォント設定
        font_group = QGroupBox("フォント")
        fg_layout = QHBoxLayout(font_group)

        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont("メイリオ"))
        self.font_combo.currentFontChanged.connect(self._on_font_changed)
        fg_layout.addWidget(self.font_combo, 3)

        self.font_size = QSpinBox()
        self.font_size.setRange(8, 200)
        self.font_size.setValue(32)
        self.font_size.setSuffix(" pt")
        self.font_size.valueChanged.connect(self._on_font_changed)
        fg_layout.addWidget(self.font_size, 1)

        self.bold_btn = QPushButton("B")
        self.bold_btn.setFont(QFont("", 11, QFont.Weight.Bold))
        self.bold_btn.setCheckable(True)
        self.bold_btn.setFixedWidth(36)
        self.bold_btn.toggled.connect(self._on_font_changed)
        fg_layout.addWidget(self.bold_btn)

        root.addWidget(font_group)

        # 色設定
        color_group = QGroupBox("色")
        cg_layout = QHBoxLayout(color_group)

        self.text_color_btn = QPushButton("文字色")
        self.text_color_btn.clicked.connect(self._pick_text_color)
        self._set_btn_color(self.text_color_btn, self._text_color)
        cg_layout.addWidget(self.text_color_btn)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        cg_layout.addWidget(sep)

        self.bg_check = QCheckBox("背景色")
        self.bg_check.setChecked(True)
        self.bg_check.toggled.connect(self._on_bg_toggle)
        cg_layout.addWidget(self.bg_check)

        self.bg_color_btn = QPushButton("背景色を選択")
        self.bg_color_btn.clicked.connect(self._pick_bg_color)
        self._set_btn_color(self.bg_color_btn, self._bg_color)
        cg_layout.addWidget(self.bg_color_btn)

        root.addWidget(color_group)

        # 操作ボタン
        btn_layout = QHBoxLayout()
        self.toggle_btn = QPushButton("オーバーレイを非表示")
        self.toggle_btn.clicked.connect(self._toggle_overlay)
        btn_layout.addWidget(self.toggle_btn)

        hint = QLabel("クリックで選択 → ハンドルでリサイズ / ドラッグで移動 / 外クリックで解除")
        hint.setStyleSheet("color: gray; font-size: 10px;")
        hint.setWordWrap(True)
        root.addWidget(hint)
        root.addLayout(btn_layout)

        self._on_font_changed()
        self.setFixedWidth(500)

    def _set_btn_color(self, btn, color):
        r, g, b = color.red(), color.green(), color.blue()
        bright = (r * 299 + g * 587 + b * 114) / 1000
        tc = "black" if bright > 128 else "white"
        btn.setStyleSheet(
            f"QPushButton {{ background-color: rgb({r},{g},{b}); color: {tc}; "
            f"border: 1px solid #aaa; padding: 4px 8px; }}"
        )

    def _on_text_changed(self):
        self.overlay.set_text(self.text_edit.toPlainText())

    def _on_font_changed(self):
        font = self.font_combo.currentFont()
        font.setPointSize(self.font_size.value())
        font.setBold(self.bold_btn.isChecked())
        self.overlay.set_font(font)

    def _pick_text_color(self):
        color = QColorDialog.getColor(self._text_color, self, "文字色を選択")
        if color.isValid():
            self._text_color = color
            self._set_btn_color(self.text_color_btn, color)
            self.overlay.set_text_color(color)

    def _pick_bg_color(self):
        color = QColorDialog.getColor(
            self._bg_color, self, "背景色を選択",
            QColorDialog.ColorDialogOption.ShowAlphaChannel
        )
        if color.isValid():
            self._bg_color = color
            self._set_btn_color(self.bg_color_btn, color)
            self.overlay.set_bg_color(color)

    def _on_bg_toggle(self, checked):
        self.bg_color_btn.setEnabled(checked)
        self.overlay.set_bg_enabled(checked)

    def _toggle_overlay(self):
        if self.overlay.isVisible():
            self.overlay.hide()
            self.toggle_btn.setText("オーバーレイを表示")
        else:
            self.overlay.show()
            self.toggle_btn.setText("オーバーレイを非表示")

    def closeEvent(self, event):
        self.overlay.close()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = ControlPanel()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
