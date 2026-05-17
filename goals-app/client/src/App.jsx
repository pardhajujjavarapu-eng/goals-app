import { useState, useEffect } from 'react';
import GoalCard from './components/GoalCard';
import GoalForm from './components/GoalForm';
import './App.css';

export default function App() {
  const [goals, setGoals] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editingGoal, setEditingGoal] = useState(null);

  useEffect(() => {
    fetch('/goals').then(r => r.json()).then(setGoals);
  }, []);

  async function handleSave(data) {
    if (editingGoal) {
      const res = await fetch(`/goals/${editingGoal.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      const updated = await res.json();
      setGoals(goals.map(g => g.id === updated.id ? updated : g));
    } else {
      const res = await fetch('/goals', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      const created = await res.json();
      setGoals([...goals, created]);
    }
    closeForm();
  }

  async function handleDelete(id) {
    await fetch(`/goals/${id}`, { method: 'DELETE' });
    setGoals(goals.filter(g => g.id !== id));
  }

  async function handleStatusChange(id, status) {
    const res = await fetch(`/goals/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    });
    const updated = await res.json();
    setGoals(goals.map(g => g.id === updated.id ? updated : g));
  }

  function handleEdit(goal) {
    setEditingGoal(goal);
    setShowForm(true);
  }

  function closeForm() {
    setShowForm(false);
    setEditingGoal(null);
  }

  const total = goals.length;
  const done = goals.filter(g => g.status === 'done').length;
  const overdue = goals.filter(g => {
    if (!g.deadline || g.status === 'done') return false;
    return new Date(g.deadline) < new Date();
  }).length;

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <h1>My Goals</h1>
          <button className="btn-primary" onClick={() => setShowForm(true)}>+ Add Goal</button>
        </div>
        <div className="stats">
          <div className="stat">
            <span className="stat-value">{total}</span>
            <span className="stat-label">Total</span>
          </div>
          <div className="stat">
            <span className="stat-value">{done}</span>
            <span className="stat-label">Completed</span>
          </div>
          <div className={`stat ${overdue > 0 ? 'overdue' : ''}`}>
            <span className="stat-value">{overdue}</span>
            <span className="stat-label">Overdue</span>
          </div>
        </div>
      </header>

      <main className="goals-grid">
        {goals.length === 0 && (
          <div className="empty-state">
            <p>No goals yet. Add your first goal to get started.</p>
          </div>
        )}
        {goals.map(goal => (
          <GoalCard
            key={goal.id}
            goal={goal}
            onEdit={handleEdit}
            onDelete={handleDelete}
            onStatusChange={handleStatusChange}
          />
        ))}
      </main>

      {showForm && (
        <GoalForm goal={editingGoal} onSave={handleSave} onCancel={closeForm} />
      )}
    </div>
  );
}
