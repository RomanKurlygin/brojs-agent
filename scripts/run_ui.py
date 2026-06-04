"""Запуск веб-интерфейса brojs-agent."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    import uvicorn

    print("brojs-agent UI: http://127.0.0.1:8765")
    print("Остановка: Ctrl+C\n")
    uvicorn.run(
        "src.ui.server:app",
        host="127.0.0.1",
        port=8765,
        reload=False,
    )
