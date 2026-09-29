"""
Todo List API - Backend
=======================
Stores todos, notes, and completed tasks.
Serves the React frontend in production.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="Todo List API")

# In development, allow React's dev server to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- In-memory storage ----------
todos = [
    {"id": 1, "text": "Learn FastAPI", "done": False},
    {"id": 2, "text": "Learn React", "done": False},
    {"id": 3, "text": "Build something cool", "done": False},
]
notes = [
    {"id": 1, "title": "Welcome!", "content": "This is my first note."},
]
next_todo_id = 4
next_note_id = 2


# ---------- Data shapes ----------
class Todo(BaseModel):
    text: str
    done: bool = False


class TodoUpdate(BaseModel):
    text: str | None = None
    done: bool | None = None


class Note(BaseModel):
    title: str
    content: str


class NoteUpdate(BaseModel):
    title: str | None = None
    content: str | None = None


# ---------- API Endpoints ----------

@app.get("/")
def home():
    return {"message": "Todo API is running!"}


@app.get("/todos")
def get_all_todos():
    return todos


@app.post("/todos")
def create_todo(todo: Todo):
    global next_todo_id
    new_todo = {"id": next_todo_id, "text": todo.text, "done": todo.done}
    todos.append(new_todo)
    next_todo_id += 1
    return new_todo


@app.patch("/todos/{todo_id}")
def update_todo(todo_id: int, update: TodoUpdate):
    for todo in todos:
        if todo["id"] == todo_id:
            if update.text is not None:
                todo["text"] = update.text
            if update.done is not None:
                todo["done"] = update.done
            return todo
    return {"error": "Todo not found"}


@app.delete("/todos/{todo_id}")
def delete_todo(todo_id: int):
    for i, todo in enumerate(todos):
        if todo["id"] == todo_id:
            todos.pop(i)
            return {"message": "Deleted!"}
    return {"error": "Todo not found"}


@app.get("/completed")
def get_completed():
    return [t for t in todos if t["done"]]


# ---------- Notes Endpoints ----------

@app.get("/notes")
def get_all_notes():
    return notes


@app.post("/notes")
def create_note(note: Note):
    global next_note_id
    new_note = {"id": next_note_id, "title": note.title, "content": note.content}
    notes.append(new_note)
    next_note_id += 1
    return new_note


@app.patch("/notes/{note_id}")
def update_note(note_id: int, update: NoteUpdate):
    for note in notes:
        if note["id"] == note_id:
            if update.title is not None:
                note["title"] = update.title
            if update.content is not None:
                note["content"] = update.content
            return note
    return {"error": "Note not found"}


@app.delete("/notes/{note_id}")
def delete_note(note_id: int):
    for i, note in enumerate(notes):
        if note["id"] == note_id:
            notes.pop(i)
            return {"message": "Deleted!"}
    return {"error": "Note not found"}


# ---------- Serve React Frontend (Production) ----------
# Check if the frontend build exists
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    # Serve static files (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        """Serve the React app for any non-API route."""
        file_path = os.path.join(frontend_dist, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        # If no file found, serve index.html (React handles routing)
        return FileResponse(os.path.join(frontend_dist, "index.html"))
