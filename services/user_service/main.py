from fastapi import FastAPI


app = FastAPI(title = "User service")

USERS = {
    1 : {"id" : 1 , "name": "Alice" , "plan" : "free"},
    2 : {"id" : 2 , "name": "Bob" , "plan" : "premium"},
    
}


@app.get("/health")
async def health():
    return {
        "status" : "User healthy"
    }


@app.get("/users/{user_id}")
async def get_user(user_id: int):
    user = USERS.get(user_id)
    return user if user else {"msg" : "No user found", "status" : 404}
 
