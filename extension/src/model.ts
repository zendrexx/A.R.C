export interface Row { label: string; description?: string; children?: Row[]; eventId?: string; path?: string; payload?: unknown }
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
  return [
    { label: state.project.name, description: 'Connected locally', children: [
      { label: state.project.path },
      { label: state.active_session ? `Session: ${state.active_session.label}` : 'No active session' },
      { label: `Collection: ${state.observer?.enabled ? state.observer.paused ? 'paused' : state.observer.running ? 'observing' : 'worker stopped' : 'disabled'}` },
      { label: `Index: ${state.index?.indexed_records ?? 0} indexed · ${state.index?.pending_records ?? 0} pending` },
      { label: 'Local chat: cited evidence · optional qwen3:1.7b source selection' },
      ...(state.observer?.error ? [{label: 'Observer error', description: state.observer.error}] : [])
    ]},
    { label: 'Tasks & verification', description: String(tasks.length), children: tasks.length ? tasks : [{label: 'No tasks recorded'}] },
    { label: 'Git changes', description: String(state.git.changed_paths.length), children: state.git.changed_paths.length ? state.git.changed_paths.map((path: string) => ({label: path, path})) : [{label: 'Working tree clean'}] },
    { label: 'Recent activity', description: 'Latest 8 records', children: events.length ? events : [{label: 'No activity recorded'}] },
    { label: 'Latest checkpoint', children: state.latest_checkpoint ? [{label: state.latest_checkpoint.id, description: state.latest_checkpoint.stale ? 'Stale · candidate unconfirmed' : 'Candidate unconfirmed', payload: state.latest_checkpoint}] : [{label: 'No checkpoint recorded'}] }
  ];
}
