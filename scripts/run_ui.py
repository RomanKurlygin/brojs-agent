"""Запуск веб-интерфейса brojs-agent."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    venv_py = ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_py.exists() and Path(sys.executable).resolve() != venv_py.resolve():
        print("Подсказка: запускайте через .venv\\Scripts\\python scripts\\run_ui.py")
        print("         (в системном Python нет зависимостей проекта)\n")

    try:
        import uvicorn
    except ModuleNotFoundError:
        print("Нет uvicorn. Установите зависимости:")
        print("  .venv\\Scripts\\pip install -r requirements.txt")
        sys.exit(1)

    print("brojs-agent UI: http://127.0.0.1:8765")
    print("Остановка: Ctrl+C\n")
    uvicorn.run(
        "src.ui.server:app",
        host="127.0.0.1",
        port=8765,
        reload=False,
    )
