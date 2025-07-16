
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
import socket
import json
import os

app = FastAPI()

HOST = '127.0.0.1'
PORT = 5050

@app.get("/")
def root():
    return FileResponse("index.html")

@app.get("/style.css")
def get_style():
    return FileResponse("style.css")

@app.get("/script.js")
def get_script():
    return FileResponse("script.js")

@app.post("/api/chat")
async def chat(request: Request):
    try:
        data = await request.json()
        user_message = data.get("message")
        if not user_message:
            return JSONResponse(content={"error": "Пустое сообщение"}, status_code=400)
        
        from plugins.example_api import sanitize_input

        sanitized_message = sanitize_input(user_message)


        with socket.create_connection((HOST, PORT), timeout=10) as sock:
            sock.sendall(json.dumps({"message": sanitized_message}).encode())
            response_data = sock.recv(4096)
            result = json.loads(response_data.decode())

        if "response" in result:
            return {"response": result["response"]}
        else:
            return JSONResponse(content={"error": result.get("error", "Агент не ответил")}, status_code=500)

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
