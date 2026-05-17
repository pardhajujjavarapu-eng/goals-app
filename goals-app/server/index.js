const express = require('express');
const cors = require('cors');
const { v4: uuidv4 } = require('uuid');
const { readGoals, writeGoals } = require('./db');

const app = express();
app.use(cors());
app.use(express.json());

app.get('/goals', (req, res) => {
  res.json(readGoals());
});

app.post('/goals', (req, res) => {
  const { title, description, deadline } = req.body;
  if (!title?.trim()) return res.status(400).json({ error: 'Title is required' });

  const goal = {
    id: uuidv4(),
    title: title.trim(),
    description: description?.trim() || '',
    deadline: deadline || null,
    status: 'todo',
    createdAt: new Date().toISOString(),
  };

  const goals = readGoals();
  goals.push(goal);
  writeGoals(goals);
  res.status(201).json(goal);
});

app.patch('/goals/:id', (req, res) => {
  const goals = readGoals();
  const idx = goals.findIndex(g => g.id === req.params.id);
  if (idx === -1) return res.status(404).json({ error: 'Goal not found' });

  goals[idx] = { ...goals[idx], ...req.body };
  writeGoals(goals);
  res.json(goals[idx]);
});

app.delete('/goals/:id', (req, res) => {
  const goals = readGoals();
  writeGoals(goals.filter(g => g.id !== req.params.id));
  res.status(204).end();
});

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => console.log(`Server running on http://localhost:${PORT}`));
