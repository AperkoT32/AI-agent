import sqlite3
import re

class DatabaseManager:
    def __init__(self, db_path='data/jane_assistant.db'):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    def add_todo(self, task: str):
        if "нужно почитать" in task.lower() or "для чтения" in task.lower():
            task = re.sub(r'(?i)(нужно\s+почитать|для\s+чтения)', '', task).strip()
            if not task.startswith('[📚]'):
                task = f"[📚 Нужно почитать] {task}"
    
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO todos (task, done) VALUES (?, ?)", (task, 0))
        conn.commit()
        conn.close()
        return f"Задача '{task}' добавлена в ваш список."
    
    def delete_todo(self, todo_id: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        conn.commit()
        if cursor.rowcount > 0:
            conn.close()
            return f"Задача с номером {todo_id} удалена из вашего списка."
        else:
            conn.close()
            return "Задача с таким номером не найдена."

    def delete_todo_by_name(self, task_name: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM todos WHERE task LIKE ? LIMIT 1", (f"%{task_name}%",))
        result = cursor.fetchone()
        
        if result:
            todo_id = result[0]
            cursor.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
            conn.commit()
            conn.close()
            return f"Задача '{task_name}' удалена из вашего списка."
        else:
            conn.close()
            return f"Задача '{task_name}' не найдена в вашем списке."

    def update_todo(self, db_id: int, done: bool):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        target_done_status = 1 if done else 0
        cursor.execute("UPDATE todos SET done = ? WHERE id = ?", (target_done_status, db_id))
        conn.commit()
        
        if cursor.rowcount > 0:
            status = "выполнена" if done else "не выполнена"
            cursor.execute("SELECT task FROM todos WHERE id = ?", (db_id,)) 
            task_info = cursor.fetchone()
            conn.close()
            if task_info:
                task_name = task_info[0]
                return f"Задача '{task_name}' помечена как {status}."
            else:
                return "Неверный номер задачи."
        else:
            conn.close()
            return "Неверный номер задачи. Пожалуйста, укажите существующий номер."

    def _get_db_id_from_ui_index(self, ui_index: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM todos ORDER BY id ASC")
        db_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        if 1 <= ui_index <= len(db_ids):
            return db_ids[ui_index - 1]
        return None

    def delete_todo_by_ui_index(self, ui_index: int):
        db_id = self._get_db_id_from_ui_index(ui_index)
        if db_id:
            return self.delete_todo(db_id)
        else:
            return "Задача с таким номером не найдена."

    def update_todo_by_ui_index(self, ui_index: int, done: bool):
        db_id = self._get_db_id_from_ui_index(ui_index)
        if db_id:
            # Вызываем старый метод update_todo с реальным ID
            return self.update_todo(db_id, done)
        else:
            return "Неверный номер задачи. Пожалуйста, укажите существующий номер."

    def mark_for_reading_by_ui_index(self, ui_index: int):
        db_id = self._get_db_id_from_ui_index(ui_index)
        if not db_id:
            return "Задача с таким номером не найдена."
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT task FROM todos WHERE id = ?", (db_id,))
        result = cursor.fetchone()
        if not result:
            conn.close()
            return "Задача с таким номером не найдена."
        task_text = result[0]
        if task_text.startswith('[📚]'):
            conn.close()
            return f"Задача '{task_text}' уже отмечена как 'нужно почитать'."
        new_task_text = f"[📚] {task_text}"
        cursor.execute("UPDATE todos SET task = ? WHERE id = ?", (new_task_text, db_id))
        conn.commit()
        conn.close()
        
        return f"Задача '{task_text}' отмечена как 'нужно почитать'."

    def get_todos(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, task, done FROM todos ORDER BY id ASC")
        todos = cursor.fetchall()
        conn.close()

        if not todos:
            return "Ваш список задач пуст."
        
        response = "Ваш текущий список задач:\n"
        for i, (item_id, task, done_status) in enumerate(todos, 1):
            status = "✅" if done_status else "⏳"
            response += f"{i}. {status} {task}\n"
        return response.strip()

    def save_chat_message(self, chat_id: str, role: str, content: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO chat_history (chat_id, role, content) VALUES (?, ?, ?)",
                    (chat_id, role, content))
        conn.commit()
        conn.close()

    def load_chat_history(self, chat_id: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT role, content FROM chat_history WHERE chat_id = ? ORDER BY timestamp ASC",
                    (chat_id,))
        history = [{"role": row[0], "content": row[1]} for row in cursor.fetchall()]
        conn.close()
        return history

    def delete_chat_history(self, chat_id: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_history WHERE chat_id = ?", (chat_id,))
        conn.commit()
        conn.close()
