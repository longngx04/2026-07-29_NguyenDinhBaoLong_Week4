"""Ứng dụng đích của bài tập tuần 4.

App này cố ý KHÔNG tự bảo vệ mình. Mọi route đều trả lời bất kỳ ai gọi tới.
Việc kiểm soát ai được gọi route nào là của gateway đứng trước nó — đó chính
là điều bài tập muốn cho thấy.
"""

from fastapi import FastAPI, HTTPException, Body

app = FastAPI(title="Week 4 Exercise Target")

ITEMS = [
    {"id": 1, "name": "cam"},
    {"id": 2, "name": "quyt"},
    {"id": 3, "name": "buoi"},
]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/items")
def list_items() -> dict:
    return {"items": ITEMS}


@app.get("/items/{item_id}")
def get_item(item_id: int) -> dict:
    for item in ITEMS:
        if item["id"] == item_id:
            return item
    raise HTTPException(status_code=404, detail="Item not found")


@app.post("/echo")
def echo(body: dict = Body(...)) -> dict:
    """Trả nguyên body nhận được, không lọc field.

    Task 9 dùng route này để phân biệt gateway có strip body hay không,
    nên app tuyệt đối không được tự ý vứt field.
    """
    return {"received": body}


@app.get("/admin")
def admin() -> dict:
    """Không nằm trong allowlist. App vẫn trả lời — gateway mới là chỗ chặn."""
    return {"secret": "khong ai duoc thay dong nay qua gateway"}


@app.get("/debug")
def debug() -> dict:
    """Cũng không nằm trong allowlist."""
    return {"env": "exercise", "note": "chi de minh hoa endpoint bi cam"}
