# 📝 Todo List App

A simple todo list, notes, and completed tasks app built with **FastAPI** and **React**.

## Features

- ✅ **Todos** — Add, check off, and delete todos
- 📒 **Notes** — Add, edit, and delete notes
- 🏆 **Completed** — View all your accomplished tasks

## Local Development

### Backend (FastAPI)
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --port 8000
```

### Frontend (React)
```bash
cd frontend
npm install
npm run dev
```

Then open http://localhost:5173

## Deploying to Render

1. Push this project to GitHub
2. Go to [render.com](https://render.com) and sign up
3. Click **New +** → **Web Service**
4. Connect your GitHub repo
5. Render will auto-detect `render.yaml` and deploy!

Your app will be live at `https://todo-app.onrender.com` (or similar URL).
