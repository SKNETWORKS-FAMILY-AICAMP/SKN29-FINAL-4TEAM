"""FastAPI 서비스 진입점 파일."""

import uvicorn
from .bootstrap import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run("ai.app.main:app", host="0.0.0.0", port=8000, reload=True)
