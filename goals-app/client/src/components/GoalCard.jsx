const STATUS_LABELS = { todo: 'To Do', 'in-progress': 'In Progress', done: 'Done' };
const NEXT_STATUS = { todo: 'in-progress', 'in-progress': 'done', done: 'todo' };

function getDaysLeft(deadline) {
  if (!deadline) return null;
  const diff = new Date(deadline) - new Date();
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

export default function GoalCard({ goal, onEdit, onDelete, onStatusChange }) {
  const daysLeft = getDaysLeft(goal.deadline);
  const isOverdue = daysLeft !== null && daysLeft < 0 && goal.status !== 'done';

  function deadlineText() {
    if (isOverdue) return `Overdue by ${Math.abs(daysLeft)} day${Math.abs(daysLeft) !== 1 ? 's' : ''}`;
    if (daysLeft === 0) return 'Due today';
    return `${daysLeft} day${daysLeft !== 1 ? 's' : ''} left`;
  }

  return (
    <div className={`goal-card status-${goal.status}`}>
      <div className="card-header">
        <span className={`status-badge ${goal.status}`}>{STATUS_LABELS[goal.status]}</span>
        <div className="card-actions">
          <button onClick={() => onEdit(goal)} title="Edit">✎</button>
          <button onClick={() => onDelete(goal.id)} title="Delete" className="btn-danger">✕</button>
        </div>
      </div>

      <h3>{goal.title}</h3>
      {goal.description && <p className="goal-desc">{goal.description}</p>}

      {goal.deadline && (
        <div className={`deadline ${isOverdue ? 'overdue' : ''}`}>
          {deadlineText()}
        </div>
      )}

      <button
        className="status-btn"
        onClick={() => onStatusChange(goal.id, NEXT_STATUS[goal.status])}
        disabled={goal.status === 'done'}
      >
        {goal.status === 'done' ? 'Completed' : `Mark ${STATUS_LABELS[NEXT_STATUS[goal.status]]}`}
      </button>
    </div>
  );
}
