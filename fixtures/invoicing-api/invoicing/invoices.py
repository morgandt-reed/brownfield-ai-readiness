from fastapi import FastAPI

app = FastAPI()


@app.post("/invoices")
def create_invoice(payload: dict) -> dict:
    return {"id": payload.get("reference"), "state": "draft"}
