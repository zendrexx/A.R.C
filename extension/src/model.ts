export interface Row { label: string; description?: string; children?: Row[]; eventId?: string; path?: string; payload?: unknown; command?: string; icon?: string }
export function memoryRows(state: any): Row[] {
  const events = (state.recent_events ?? []).map((e: any) => ({
    label: e.summary, description: `${e.kind} · ${new Date(e.created_at).toLocaleString()}`,
    eventId: e.id
  }));
  const tasks = (state.tasks ?? []).map((t: any) => ({
    label: t.title, description: t.state.replaceAll('_', ' '), children: [
      { label: t.agent_claim ? `Unverified claim: ${t.agent_claim}` : 'No agent claim recorded' },
      { label: t.tests_are_current ? 'Named tests are current' : 'No current passing test evidence' },
      ...[...t.implementation_event_ids, ...t.current_passing_test_event_ids].map(id => ({label: `Evidence · ${id}`, eventId: id}))
    ]
  }));
  const handoff = state.handoff;
  const previous = handoff?.previous_session;
  const handoffRows: Row[] = handoff ? [
    {label: handoff.overview || 'No recorded work yet'},
    ...(handoff.suggested_next_task ? [{label: `Next: ${handoff.suggested_next_task.title}`, description: handoff.suggested_next_task.state}] : []),
    ...(previous ? [{label: `Previous session: ${previous.session.label}`, description: `${previous.total_events} evidence records`, children: (previous.recent_evidence ?? []).map((e: any) => ({label: e.summary, description: e.kind, eventId: e.id}))}] : []),
    ...(handoff.last_test ? [{label: `Last test: ${handoff.last_test.passed ? 'passed' : 'failed'}`, description: handoff.last_test.current ? 'Current Git state' : 'Stale after Git changes', eventId: handoff.last_test.event_id}] : []),
    ...(handoff.key_evidence ?? []).slice(0, 6).map((e: any) => ({label: e.summary, description: e.kind, eventId: e.id}))
  ] : [{label: 'Handoff unavailable'}];
  return [
    { label: state.project.name, description: 'Connected locally', children: [
      { label: state.project.path },
      { label: `Branch: ${state.git.branch || 'unknown'}` },
      { label: state.active_session ? `Session: ${state.active_session.label}` : 'No active session' },
      { label: `Collection: ${state.observer?.enabled ? state.observer.paused ? 'paused' : state.observer.running ? 'observing' : 'worker stopped' : 'disabled'}` },
      { label: `Index: ${state.index?.indexed_records ?? 0} indexed · ${state.index?.pending_records ?? 0} pending` },
      { label: 'Local chat: recorded evidence with your selected model' },
      ...(state.observer?.error ? [{label: 'Observer error', description: state.observer.error}] : [])
    ]},
    { label: 'Tasks & verification', description: String(tasks.length), children: tasks.length ? tasks : [{label: 'No tasks recorded'}] },
    { label: 'Handoff', description: previous ? 'Previous session available' : 'Current project state', children: handoffRows },
    { label: 'Git changes', description: String(state.git.changed_paths.length), children: state.git.changed_paths.length ? state.git.changed_paths.map((path: string) => ({label: path, path})) : [{label: 'Working tree clean'}] },
    { label: 'Timeline', description: 'Latest 8 records', children: events.length ? [...events, {label: 'Open full timeline…', command: 'arc.timeline'}] : [{label: 'No activity recorded'}] },
    { label: 'Latest checkpoint', children: state.latest_checkpoint ? [{label: state.latest_checkpoint.id, description: state.latest_checkpoint.stale ? 'Stale · candidate unconfirmed' : 'Candidate unconfirmed', payload: state.latest_checkpoint}] : [{label: 'No checkpoint recorded'}] },
    ...(state.handoff ? [{label: 'Session handoff', payload: state.handoff}] : [])
  ];
}
