/*
  Todo List App - Frontend (React)
  =================================
  3 Tabs:
  1. Todos    — add, toggle, delete todos
  2. Notes    — add, edit, delete notes
  3. Completed — shows all accomplished tasks
*/

import { useState, useEffect } from 'react'

const API = 'http://localhost:8000'

function App() {
  const [activeTab, setActiveTab] = useState('todos')

  return (
    <div className="container">
      <h1>📝 My Planner</h1>

      {/* ----- Tab Navigation ----- */}
      <div className="tabs">
        <button
          className={activeTab === 'todos' ? 'tab active' : 'tab'}
          onClick={() => setActiveTab('todos')}
        >
          ✅ Todos
        </button>
        <button
          className={activeTab === 'notes' ? 'tab active' : 'tab'}
          onClick={() => setActiveTab('notes')}
        >
          📒 Notes
        </button>
        <button
          className={activeTab === 'completed' ? 'tab active' : 'tab'}
          onClick={() => setActiveTab('completed')}
        >
          🏆 Completed
        </button>
      </div>

      {/* ----- Tab Content ----- */}
      {activeTab === 'todos' && <TodosTab />}
      {activeTab === 'notes' && <NotesTab />}
      {activeTab === 'completed' && <CompletedTab />}
    </div>
  )
}

/* ========================================
   TAB 1: TODOS
   ======================================== */
function TodosTab() {
  const [todos, setTodos] = useState([])
  const [newText, setNewText] = useState('')

  useEffect(() => {
    fetch(`${API}/todos`)
      .then((res) => res.json())
      .then(setTodos)
  }, [])

  function addTodo() {
    if (!newText.trim()) return
    fetch(`${API}/todos`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: newText, done: false }),
    })
      .then((res) => res.json())
      .then((todo) => {
        setTodos([...todos, todo])
        setNewText('')
      })
  }

  function toggleDone(todo) {
    fetch(`${API}/todos/${todo.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ done: !todo.done }),
    })
      .then((res) => res.json())
      .then((updated) => {
        setTodos(todos.map((t) => (t.id === updated.id ? updated : t)))
      })
  }

  function deleteTodo(id) {
    fetch(`${API}/todos/${id}`, { method: 'DELETE' }).then(() => {
      setTodos(todos.filter((t) => t.id !== id))
    })
  }

  return (
    <div>
      <div className="add-row">
        <input
          type="text"
          placeholder="What do you need to do?"
          value={newText}
          onChange={(e) => setNewText(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && addTodo()}
        />
        <button onClick={addTodo}>Add</button>
      </div>

      <ul className="todo-list">
        {todos.map((todo) => (
          <li key={todo.id} className={todo.done ? 'done' : ''}>
            <label>
              <input
                type="checkbox"
                checked={todo.done}
                onChange={() => toggleDone(todo)}
              />
              <span>{todo.text}</span>
            </label>
            <button className="delete" onClick={() => deleteTodo(todo.id)}>
              ✕
            </button>
          </li>
        ))}
      </ul>

      {todos.length === 0 && <p className="empty">No todos yet — add one above!</p>}
    </div>
  )
}

/* ========================================
   TAB 2: NOTES
   ======================================== */
function NotesTab() {
  const [notes, setNotes] = useState([])
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [editingId, setEditingId] = useState(null)
  const [editTitle, setEditTitle] = useState('')
  const [editContent, setEditContent] = useState('')

  useEffect(() => {
    fetch(`${API}/notes`)
      .then((res) => res.json())
      .then(setNotes)
  }, [])

  function addNote() {
    if (!title.trim() || !content.trim()) return
    fetch(`${API}/notes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, content }),
    })
      .then((res) => res.json())
      .then((note) => {
        setNotes([...notes, note])
        setTitle('')
        setContent('')
      })
  }

  function startEdit(note) {
    setEditingId(note.id)
    setEditTitle(note.title)
    setEditContent(note.content)
  }

  function saveEdit(id) {
    fetch(`${API}/notes/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: editTitle, content: editContent }),
    })
      .then((res) => res.json())
      .then((updated) => {
        setNotes(notes.map((n) => (n.id === updated.id ? updated : n)))
        setEditingId(null)
      })
  }

  function deleteNote(id) {
    fetch(`${API}/notes/${id}`, { method: 'DELETE' }).then(() => {
      setNotes(notes.filter((n) => n.id !== id))
    })
  }

  return (
    <div>
      {/* Add note form */}
      <div className="note-form">
        <input
          type="text"
          placeholder="Note title..."
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <textarea
          placeholder="Write your note..."
          value={content}
          onChange={(e) => setContent(e.target.value)}
          rows={3}
        />
        <button onClick={addNote}>Add Note</button>
      </div>

      {/* Notes list */}
      <div className="notes-list">
        {notes.map((note) => (
          <div key={note.id} className="note-card">
            {editingId === note.id ? (
              /* ----- Edit Mode ----- */
              <div className="note-edit">
                <input
                  type="text"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                />
                <textarea
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  rows={3}
                />
                <div className="note-actions">
                  <button className="save-btn" onClick={() => saveEdit(note.id)}>
                    Save
                  </button>
                  <button className="cancel-btn" onClick={() => setEditingId(null)}>
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              /* ----- View Mode ----- */
              <>
                <h3>{note.title}</h3>
                <p>{note.content}</p>
                <div className="note-actions">
                  <button className="edit-btn" onClick={() => startEdit(note)}>
                    Edit
                  </button>
                  <button className="delete-btn" onClick={() => deleteNote(note.id)}>
                    Delete
                  </button>
                </div>
              </>
            )}
          </div>
        ))}
      </div>

      {notes.length === 0 && <p className="empty">No notes yet — add one above!</p>}
    </div>
  )
}

/* ========================================
   TAB 3: COMPLETED TASKS
   ======================================== */
function CompletedTab() {
  const [completed, setCompleted] = useState([])

  useEffect(() => {
    fetch(`${API}/completed`)
      .then((res) => res.json())
      .then(setCompleted)
  }, [])

  return (
    <div>
      <h2 className="section-title">🏆 Accomplished Tasks</h2>
      <ul className="todo-list">
        {completed.map((todo) => (
          <li key={todo.id} className="done">
            <label>
              <input type="checkbox" checked readOnly />
              <span>{todo.text}</span>
            </label>
          </li>
        ))}
      </ul>

      {completed.length === 0 && (
        <p className="empty">Nothing completed yet — check off some todos!</p>
      )}
    </div>
  )
}

export default App
