import uuid
from typing import Dict, Set, Optional, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# 정적 파일 서빙 (/static/...)
app.mount("/static", StaticFiles(directory="static"), name="static")

# -----------------------------
# In-memory room state
# -----------------------------
class Room:
    def __init__(self) -> None:
        self.clients: Set[WebSocket] = set()
        self.client_ids: Dict[WebSocket, str] = {}
        self.controller_id: Optional[str] = None  # takeover 방식: 마지막으로 ON 누른 사람
        self.pdf_id: int = 1
        self.page: int = 1
        self.total_pdfs: int = 3

rooms: Dict[str, Room] = {}


def get_room(room_id: str) -> Room:
    if room_id not in rooms:
        rooms[room_id] = Room()
    return rooms[room_id]


async def broadcast(room: Room, payload: Dict[str, Any]) -> None:
    dead = []
    for ws in list(room.clients):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        room.clients.discard(ws)
        room.client_ids.pop(ws, None)


def clamp_page(p: int) -> int:
    if p < 1:
        return 1
    if p > 9999:
        return 9999
    return p


def clamp_pdf_id(pdf_id: int, total: int) -> int:
    if pdf_id < 1:
        return 1
    if pdf_id > total:
        return total
    return pdf_id


def room_snapshot(room: Room) -> Dict[str, Any]:
    return {
        "type": "snapshot",
        "controller_id": room.controller_id,
        "pdf_id": room.pdf_id,
        "page": room.page,
        "total_pdfs": room.total_pdfs,
    }


# -----------------------------
# Pages
# -----------------------------
@app.get("/")
def index():
    return {
        "ok": True,
        "usage": {
            "host": "/host?room=abcd",
            "viewer": "/view?room=abcd",
        }
    }


@app.get("/host")
def host_page():
    with open("static/host.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/view")
def view_page():
    with open("static/view.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


# -----------------------------
# WebSocket endpoint
# -----------------------------
@app.websocket("/ws/{room_id}")
async def ws_room(ws: WebSocket, room_id: str):
    await ws.accept()
    room = get_room(room_id)

    room.clients.add(ws)

    # client_id 부여 (새로고침 시 바뀔 수 있음 - 필요하면 localStorage로 고정 가능)
    client_id = str(uuid.uuid4())
    room.client_ids[ws] = client_id

    # 접속자에게 본인 id + 현재 스냅샷 제공
    await ws.send_json({"type": "hello", "client_id": client_id})
    await ws.send_json(room_snapshot(room))

    # 다른 사람에게도 "누가 들어왔다" 까지는 굳이 방송 안 해도 됨(최소 기능)
    try:
        while True:
            msg = await ws.receive_json()
            mtype = msg.get("type")

            # 1) 조정 ON (즉시 takeover)
            if mtype == "controller_on":
                room.controller_id = client_id
                await broadcast(room, {"type": "controller_changed", "controller_id": room.controller_id})
                # 동시에 스냅샷도 방송(클라이언트 UI 동기화 안정성)
                await broadcast(room, room_snapshot(room))

            # 2) 조정 OFF (옵션: 그냥 controller 비우기)
            elif mtype == "controller_off":
                # takeover 방식에서는 OFF가 꼭 필요하지 않지만,
                # 원하면 "비움" 상태로 전환 가능
                if room.controller_id == client_id:
                    room.controller_id = None
                    await broadcast(room, {"type": "controller_changed", "controller_id": None})
                    await broadcast(room, room_snapshot(room))

            # 3) 상태 변경 (pdf/page) - controller만 허용
            elif mtype == "set_state":
                if room.controller_id != client_id:
                    # 조정자가 아닌데 변경 시도 -> 거절
                    await ws.send_json({"type": "error", "message": "현재 조정자가 아닙니다. 조정 ON을 누르세요."})
                    continue

                pdf_id = int(msg.get("pdf_id", room.pdf_id))
                page = int(msg.get("page", room.page))

                room.pdf_id = clamp_pdf_id(pdf_id, room.total_pdfs)
                room.page = clamp_page(page)

                await broadcast(room, {"type": "state_changed", "pdf_id": room.pdf_id, "page": room.page})
                await broadcast(room, room_snapshot(room))

            # 4) keepalive (선택)
            elif mtype == "ping":
                await ws.send_json({"type": "pong"})

    except WebSocketDisconnect:
        room.clients.discard(ws)
        room.client_ids.pop(ws, None)

        # 조정자가 나가면 controller 비움
        if room.controller_id == client_id:
            room.controller_id = None
            await broadcast(room, {"type": "controller_changed", "controller_id": None})
            await broadcast(room, room_snapshot(room))
