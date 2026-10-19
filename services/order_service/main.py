from fastapi import FastAPI, HTTPException

app = FastAPI(title="GateKeeper Order Service")

ORDERS = {
    101: {
        "id": 101,
        "user_id": 1,
        "product_id": 1,
        "quantity": 2,
        "status": "created",
    },
    102: {
        "id": 102,
        "user_id": 2,
        "product_id": 2,
        "quantity": 1,
        "status": "processing",
    },
}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "order-service"}


@app.get("/orders/{order_id}")
async def get_order(order_id: int):
    order = ORDERS.get(order_id)
    return order if order else {"msg" : "order not found", "staus" : 404}