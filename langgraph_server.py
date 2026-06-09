from __future__ import annotations

from fastapi import FastAPI


app = FastAPI()


@app.get("/ok")
def ok():
    return {"status": "ok"}
