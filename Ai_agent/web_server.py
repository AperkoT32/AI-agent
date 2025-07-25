from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from plugins.db_manager import DatabaseManager 
import socket
import json
import os
from typing import Optional
import config.config_setting as config_setting

class SafeJSONResponse(JSONResponse):
    def init_headers(self, headers: dict) -> None:
        safe_headers = {}
        for k, v in (headers or {}).items():
            try:
                k.encode("latin-1")
                v.encode("latin-1")
                safe_headers[k] = v
            except UnicodeEncodeError:
                print(f"⚠️ Удалён проблемный заголовок: {k}: {v}")
                continue
        super().init_headers(safe_headers)

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

HOST = config_setting.API_HOST 
PORT = config_setting.API_PORT 
IMAGES_DIR = config_setting.IMAGES_DIR # 

os.makedirs(IMAGES_DIR, exist_ok=True)

if os.path.exists(config_setting.GIFT_DIR):
    app.mount("/gift", StaticFiles(directory="data/gift"), name="gift")

db_manager = DatabaseManager(db_path=config_setting.DATABASE_PATH)

@app.get("/")
def root():
    return FileResponse("templates/index.html")


@app.get("/style.css")
def get_style():
    return FileResponse("static/style.css")

@app.get("/script.js")
def get_script():
    return FileResponse("static/script.js")


@app.post("/api/chat")
async def chat(
    request: Request,
    file: Optional[UploadFile] = File(None),
    message: Optional[str] = Form(None),
    chat_id: Optional[str] = Form(None)
):
    try:
        user_message = ""
        
        if file and file.filename:

            file_path = os.path.join(IMAGES_DIR, file.filename)
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            
            if message and message.strip():
                user_message = f"!import {file.filename}\\n{message}"
            else:
                user_message = f"!import {file.filename}\\nОпишите это изображение"
            
        elif message:
            user_message = message
        else:
            try:
                data = await request.json()
                user_message = data.get("message", "")
                chat_id = data.get("chat_id", chat_id) 
            except:
                return SafeJSONResponse(content={"error": "Пустое сообщение"}, status_code=400)
            
        if not user_message:
            return SafeJSONResponse(content={"error": "Пустое сообщение"}, status_code=400)

        if chat_id: # Сохраняем сообщение пользователя в БД
            db_manager.save_chat_message(chat_id, "user", user_message)

        try:
            from plugins.example_api import sanitize_input
            sanitized_message = sanitize_input(user_message)
        except ImportError:
            sanitized_message = user_message

        with socket.create_connection((HOST, PORT), timeout=30) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)  # Увеличиваем размер буфера
            request_data = json.dumps({"message": sanitized_message, "chat_id": chat_id}) #  Передаем chat_id
            sock.sendall(request_data.encode())
            
            chunks = []
            while True:
                chunk = sock.recv(8096)
                if not chunk:
                    break
                chunks.append(chunk)
            response_data = b''.join(chunks)
            
            try:
                result = json.loads(response_data.decode('utf-8'))
            except json.JSONDecodeError as e:
                print(f"[ERROR] JSON decode error: {e}")
                print(f"Raw response: {response_data.decode('utf-8', errors='replace')}")
                return SafeJSONResponse(content={"error": "Ошибка обработки ответа"}, status_code=500)

        if chat_id:
            if result and "response" in result and result["response"]:
                db_manager.save_chat_message(chat_id, "assistant", result["response"])
            else:
                # Если ответ пустой, сохраняем сообщение об ошибке
                error_message = "Извините, не удалось получить ответ."
                db_manager.save_chat_message(chat_id, "assistant", error_message)
                result = {"response": error_message}

        if "response" in result:
            return {"response": result["response"]}
        else:
            return SafeJSONResponse(content={"error": result.get("error", "Агент не ответил")}, status_code=500)

    except Exception as e:
        print(f"[ERROR] Ошибка в /api/chat: {e}")
        import traceback
        traceback.print_exc()
        return SafeJSONResponse(content={"error": str(e)}, status_code=500)
    

@app.get("/api/chat_history/{chat_id}")
async def get_chat_history(chat_id: str):
    try:
        history = db_manager.load_chat_history(chat_id)
        return SafeJSONResponse(content={"history": history})
    except Exception as e:
        print(f"[ERROR] Ошибка при загрузке истории чата для {chat_id}: {e}")
        return SafeJSONResponse(content={"error": str(e)}, status_code=500)

@app.delete("/api/chat_history/{chat_id}")
async def delete_chat_history(chat_id: str):
    try:
        db_manager.delete_chat_history(chat_id)
        return SafeJSONResponse(content={"message": f"История чата для {chat_id} удалена."})
    except Exception as e:
        print(f"[ERROR] Ошибка при удалении истории чата для {chat_id}: {e}")
        return SafeJSONResponse(content={"error": str(e)}, status_code=500)
