const fs = require('fs');
const path = require('path');

const DB_FILE = path.join(__dirname, 'data.json');

function readGoals() {
  if (!fs.existsSync(DB_FILE)) return [];
  return JSON.parse(fs.readFileSync(DB_FILE, 'utf8'));
}

function writeGoals(goals) {
  fs.writeFileSync(DB_FILE, JSON.stringify(goals, null, 2));
}

module.exports = { readGoals, writeGoals };
