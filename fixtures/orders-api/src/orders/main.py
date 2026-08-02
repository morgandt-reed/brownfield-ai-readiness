from fastapi import FastAPI

app = FastAPI()


@app.get("/orders/{order_id}")
def get_order(order_id: int) -> dict:
    return {"id": order_id, "status": "open"}
