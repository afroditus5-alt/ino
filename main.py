"""
ReelsForge — main entry point.
Запуск: python main.py
Или собрать в exe:  python -m nuitka --standalone --enable-plugin=pyqt6 --windows-console-mode=disable main.py
"""
import sys, os, asyncio
from pathlib import Path

# Windows: правильная политика event loop для asyncio + Qt
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Убедимся, что ffmpeg найдётся (положи ffmpeg.exe рядом с exe или в PATH)
_bin = Path(__file__).parent / "bin"
if _bin.exists():
    os.environ["PATH"] = str(_bin) + os.pathsep + os.environ["PATH"]

# папки под данные
for d in ("data", "logs", "cache", "assets"):
    Path(d).mkdir(exist_ok=True)

# devices.json — если нет, создадим стартовый
_devices_file = Path("assets/devices.json")
if not _devices_file.exists():
    from assets.gen_devices import generate_starter_pool
    generate_starter_pool(_devices_file)


def main():
    from PyQt6.QtWidgets import QApplication
    import qasync
    from gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("ReelsForge")
    app.setStyle("Fusion")

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    w = MainWindow()
    w.show()

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()