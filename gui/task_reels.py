from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QGroupBox, QLineEdit, QPushButton, QCheckBox,
                             QFileDialog, QLabel, QPlainTextEdit, QSpinBox,
                             QComboBox, QMessageBox)
from pathlib import Path


class ReelsUploadPanel(QWidget):
    def __init__(self):
        super().__init__()
        v = QVBoxLayout(self)

        # ─── Видео ───
        gb_video = QGroupBox("Видео")
        fv = QFormLayout(gb_video)

        h = QHBoxLayout()
        self.video_path = QLineEdit()
        self.video_path.setPlaceholderText("Путь к MP4 / MOV / M4V…")
        btn = QPushButton("Обзор…")
        btn.clicked.connect(self._pick_video)
        h.addWidget(self.video_path)
        h.addWidget(btn)
        fv.addRow("Файл:", h)

        h2 = QHBoxLayout()
        self.folder_path = QLineEdit()
        self.folder_path.setPlaceholderText(
            "Папка с видео — случайный выбор на каждый акк (опционально)"
        )
        btn2 = QPushButton("Обзор…")
        btn2.clicked.connect(self._pick_folder)
        h2.addWidget(self.folder_path)
        h2.addWidget(btn2)
        fv.addRow("Папка:", h2)

        v.addWidget(gb_video)

        # ─── Описание ───
        gb_cap = QGroupBox("Описание (caption)")
        fc = QVBoxLayout(gb_cap)
        self.caption = QPlainTextEdit()
        self.caption.setPlaceholderText(
            "Поддержка спинтакса: {вар1|вар2|вар3}\n"
            "Пример: {Красивое|Топ|Огонь} видео! #reels #{аниме|мемы}"
        )
        self.caption.setMaximumHeight(120)
        fc.addWidget(self.caption)

        hbtn = QHBoxLayout()
        self.btn_jp_boost = QPushButton("＋ Вставить JP аниме-бустер")
        self.btn_jp_boost.clicked.connect(self._insert_jp_boost)
        hbtn.addWidget(self.btn_jp_boost)
        hbtn.addStretch()
        fc.addLayout(hbtn)

        v.addWidget(gb_cap)
        # ─── Кастомная обложка (мисс-клик) ───
        gb_cover = QGroupBox("Обложка (для мисс-клика — cover ≠ видео)")
        fcov = QFormLayout(gb_cover)

        info = QLabel(
            "Если папка указана — на каждый залив берётся случайная картинка "
            "как обложка вместо первого кадра видео. Это даёт мисс-клик эффект "
            "(в ленте виден cover, при тапе играет видео)."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#8ab4ff;")
        fcov.addRow(info)

        h_cov = QHBoxLayout()
        self.cover_folder = QLineEdit()
        self.cover_folder.setPlaceholderText(
            "Папка с обложками (JPG/PNG, 1080x1920 или квадрат) — опционально"
        )
        btn_cov = QPushButton("Обзор…")
        btn_cov.clicked.connect(self._pick_cover_folder)
        h_cov.addWidget(self.cover_folder)
        h_cov.addWidget(btn_cov)
        fcov.addRow("Папка обложек:", h_cov)

        v.addWidget(gb_cover)
        # ─── Уникализация ───
        gb_uniq = QGroupBox("Уникализация видео")
        fu = QFormLayout(gb_uniq)
        self.uniq_enable = QCheckBox("Уникализировать перед заливкой (ffmpeg)")
        self.uniq_enable.setChecked(True)
        fu.addRow(self.uniq_enable)

        self.uniq_level = QComboBox()
        self.uniq_level.addItems([
            "Fast (remux + метаданные) — ~0.5с, слабое изменение pHash",
            "Universal (trim + crop + аудио) — ~2-4с, РЕКОМЕНДУЕТСЯ",
            "Light (нежное изменение) — ~3-5с",
            "Medium (сильнее + eq + rotate) — ~5-8с",
            "Heavy (максимум, не для 70 потоков) — ~10-15с",
        ])
        self.uniq_level.setCurrentIndex(1)   # Universal по умолчанию
        fu.addRow("Уровень:", self.uniq_level)

        self.uniq_reencode_audio = QCheckBox("Ре-кодировать аудио")
        self.uniq_reencode_audio.setChecked(True)
        fu.addRow(self.uniq_reencode_audio)

        v.addWidget(gb_uniq)

        # ─── First setup ───
        gb_first = QGroupBox("Первый вход (только для новых аккаунтов)")
        ff = QFormLayout(gb_first)

        self.first_setup_enable = QCheckBox(
            "Ставить био (из вкладки Био) перед первым заливом"
        )
        self.first_setup_enable.setChecked(True)
        ff.addRow(self.first_setup_enable)

        self.first_setup_avatar = QCheckBox(
            "Ставить аватарку перед первым заливом"
        )
        self.first_setup_avatar.setChecked(False)
        ff.addRow(self.first_setup_avatar)

        h_ava = QHBoxLayout()
        self.avatar_folder = QLineEdit()
        self.avatar_folder.setPlaceholderText(
            "Папка с аватарками (JPG/PNG)"
        )
        btn_ava = QPushButton("Обзор…")
        btn_ava.clicked.connect(self._pick_avatar_folder)
        h_ava.addWidget(self.avatar_folder)
        h_ava.addWidget(btn_ava)
        ff.addRow("Папка аватарок:", h_ava)

        info = QLabel(
            "Оба действия проверяют что уже стоит (по хэшу). "
            "Если стоит то же био/аватар — пропускается автоматически."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#8ab4ff;")
        ff.addRow(info)

        v.addWidget(gb_first)

        # ─── Публикация ───
        gb_pub = QGroupBox("Настройки публикации")
        fp = QFormLayout(gb_pub)
        self.share_feed = QCheckBox("Публиковать также в основную ленту")
        self.disable_comments = QCheckBox("Отключить комментарии")
        self.hide_like_count = QCheckBox("Скрыть счётчик лайков")
        fp.addRow(self.share_feed)
        fp.addRow(self.disable_comments)
        fp.addRow(self.hide_like_count)

        self.delay_min = QSpinBox(); self.delay_min.setRange(0, 3600); self.delay_min.setValue(25)
        self.delay_max = QSpinBox(); self.delay_max.setRange(0, 3600); self.delay_max.setValue(90)
        dh = QHBoxLayout()
        dh.addWidget(self.delay_min)
        dh.addWidget(QLabel("—"))
        dh.addWidget(self.delay_max)
        dh.addWidget(QLabel("сек между акками"))
        fp.addRow("Задержки:", dh)

        self.warmup_intensity = QComboBox()
        self.warmup_intensity.addItems([
            "Минимум (3 запроса)",
            "Средний (6-8 запросов)   — рекомендуется",
            "Максимум (12-15 запросов)",
        ])
        self.warmup_intensity.setCurrentIndex(1)
        fp.addRow("Прогрев сессии:", self.warmup_intensity)

        self.retry_count = QSpinBox()
        self.retry_count.setRange(0, 10)
        self.retry_count.setValue(1)
        fp.addRow("Повторов при ошибке:", self.retry_count)

        self.rotate_proxy_on_ban = QCheckBox("Ротировать прокси при чекпоинте/бане")
        self.rotate_proxy_on_ban.setChecked(True)
        fp.addRow(self.rotate_proxy_on_ban)

        v.addWidget(gb_pub)
        v.addStretch()

        # ─── Persist ───
        self.load_settings()
        self._wire_autosave()

    # ============================================================
    def _pick_video(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "Видео",
            filter="Video (*.mp4 *.mov *.m4v *.mkv *.webm)"
        )
        if p:
            self.video_path.setText(p)

    def _pick_folder(self):
        p = QFileDialog.getExistingDirectory(self, "Папка с видео")
        if p:
            self.folder_path.setText(p)

    def _insert_jp_boost(self):
        txt = ("『ONE PIECE』エルバフ編最新情報を発表＆最新PV公開\n"
               "オープニング主題歌＆エンディング主題歌\n"
               "#anime #onepiece #アニメ #漫画 #reels #fyp")
        cur = self.caption.toPlainText()
        self.caption.setPlainText((cur + "\n\n" + txt).strip())
    def _pick_cover_folder(self):
        p = QFileDialog.getExistingDirectory(self, "Папка с обложками")
        if p:
            self.cover_folder.setText(p)
    def _pick_avatar_folder(self):
        p = QFileDialog.getExistingDirectory(self, "Папка с аватарками")
        if p:
            self.avatar_folder.setText(p)
    # ============================================================
    def get_task(self):
        video = self.video_path.text().strip()
        folder = self.folder_path.text().strip()

        if not video and not folder:
            QMessageBox.warning(self, "!", "Укажи файл или папку с видео")
            return None, None
        if video and not Path(video).exists():
            QMessageBox.warning(self, "!", "Файл не найден")
            return None, None
        if folder and not Path(folder).is_dir():
            QMessageBox.warning(self, "!", "Папка не найдена")
            return None, None

        return "upload_reel", {
            "video_path":          video or None,
            "video_folder":        folder or None,
            "caption":             self.caption.toPlainText(),
            "uniquify":            self.uniq_enable.isChecked(),
            "uniquify_level": ["fast", "universal", "light", "medium", "heavy"][self.uniq_level.currentIndex()],
            "uniquify_audio":      self.uniq_reencode_audio.isChecked(),
            "share_to_feed":       self.share_feed.isChecked(),
            "disable_comments":    self.disable_comments.isChecked(),
            "hide_like_count":     self.hide_like_count.isChecked(),
            "cover_folder":       self.cover_folder.text().strip(),
            "delay_min":           self.delay_min.value(),
            "delay_max":           self.delay_max.value(),
            "first_setup_enable":  self.first_setup_enable.isChecked(),
            "first_setup_avatar":  self.first_setup_avatar.isChecked(),
            "avatar_folder":       self.avatar_folder.text().strip(),
            "warmup":              ["min", "medium", "max"][self.warmup_intensity.currentIndex()],
            "retry":               self.retry_count.value(),
            "rotate_proxy_on_ban": self.rotate_proxy_on_ban.isChecked(),
            "first_setup_enable":  self.first_setup_enable.isChecked(),
            
        }

    # ============================================================ Persist
    def _wire_autosave(self):
        for w in (self.video_path, self.folder_path, self.avatar_folder, self.cover_folder):
            w.textChanged.connect(self.save_settings)
        self.caption.textChanged.connect(self.save_settings)

        for cb in (self.uniq_enable, self.uniq_reencode_audio, self.share_feed,
                   self.disable_comments, self.hide_like_count,
                   self.rotate_proxy_on_ban, self.first_setup_avatar, self.first_setup_enable):
            cb.stateChanged.connect(self.save_settings)

        self.uniq_level.currentIndexChanged.connect(self.save_settings)
        self.warmup_intensity.currentIndexChanged.connect(self.save_settings)

        for sp in (self.delay_min, self.delay_max, self.retry_count):
            sp.valueChanged.connect(self.save_settings)

    def _cfg_path(self):
        p = Path(__file__).resolve().parent.parent / "data" / "reels_settings.json"
        p.parent.mkdir(exist_ok=True)
        return p

    def save_settings(self):
        import json
        try:
            self._cfg_path().write_text(json.dumps({
                "video_path":         self.video_path.text(),
                "folder_path":        self.folder_path.text(),
                "caption":            self.caption.toPlainText(),
                "uniq_enable":        self.uniq_enable.isChecked(),
                "uniq_level":         self.uniq_level.currentIndex(),
                "uniq_audio":         self.uniq_reencode_audio.isChecked(),
                "share_feed":         self.share_feed.isChecked(),
                "disable_comm":       self.disable_comments.isChecked(),
                "hide_likes":         self.hide_like_count.isChecked(),
                "delay_min":          self.delay_min.value(),
                "cover_folder": self.cover_folder.text(),
                "delay_max":          self.delay_max.value(),
                "first_setup_enable": self.first_setup_enable.isChecked(),
                "first_setup_avatar": self.first_setup_avatar.isChecked(),
                "avatar_folder":      self.avatar_folder.text(),
                "warmup":             self.warmup_intensity.currentIndex(),
                "retry":              self.retry_count.value(),
                "rotate_proxy":       self.rotate_proxy_on_ban.isChecked(),
                
            }, ensure_ascii=False, indent=2), "utf-8")
        except Exception as e:
            print(f"[reels save] {e}")

    def load_settings(self):
        import json
        p = self._cfg_path()
        if not p.exists():
            return
        try:
            cfg = json.loads(p.read_text("utf-8"))
        except Exception as e:
            print(f"[reels load] {e}")
            return
        self.video_path.setText(cfg.get("video_path", ""))
        self.folder_path.setText(cfg.get("folder_path", ""))
        self.caption.setPlainText(cfg.get("caption", ""))
        self.uniq_enable.setChecked(cfg.get("uniq_enable", True))
        self.uniq_level.setCurrentIndex(cfg.get("uniq_level", 0))
        self.uniq_reencode_audio.setChecked(cfg.get("uniq_audio", True))
        self.share_feed.setChecked(cfg.get("share_feed", False))
        self.first_setup_enable.setChecked(cfg.get("first_setup_enable", True))
        self.first_setup_avatar.setChecked(cfg.get("first_setup_avatar", False))
        self.avatar_folder.setText(cfg.get("avatar_folder", ""))
        self.cover_folder.setText(cfg.get("cover_folder", ""))
        self.disable_comments.setChecked(cfg.get("disable_comm", False))
        self.hide_like_count.setChecked(cfg.get("hide_likes", False))
        self.delay_min.setValue(cfg.get("delay_min", 25))
        self.delay_max.setValue(cfg.get("delay_max", 90))
        self.warmup_intensity.setCurrentIndex(cfg.get("warmup", 1))
        self.retry_count.setValue(cfg.get("retry", 1))
        self.rotate_proxy_on_ban.setChecked(cfg.get("rotate_proxy", True))
        self.first_setup_enable.setChecked(cfg.get("first_setup_enable", True))
        