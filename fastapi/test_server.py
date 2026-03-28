from fastapi import FastAPI, Request
from pydantic import BaseModel
import uvicorn

app = FastAPI()


class Ping(BaseModel):
    msg: str
    device: str
    id: str


@app.post("/ping")
async def receive_ping(p: Ping):
    print(f"Received ping from {p.device} id={p.id} msg={p.msg}")
    return {"status": "ok", "received": p.dict()}


if __name__ == "__main__":
    uvicorn.run("test_server:app", host="0.0.0.0", port=8000, log_level="info")
