from fastapi import FastAPI, HTTPException

app = FastAPI(title="GateKeeper Product Service")

PRODUCTS = {
    1: {"id": 1, "name": "Keyboard", "price": 2500},
    2: {"id": 2, "name": "Monitor", "price": 8000},
}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "product-service"}


@app.get("/products/{product_id}")
async def get_product(product_id: int):
    product = PRODUCTS.get(product_id)
    return product if product else {"msg" : "product not found", "status" : 404}
