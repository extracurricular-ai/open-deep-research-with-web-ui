import { html } from '../htm.js';
import { useStore, loadSession, deleteSession, newSession, toggleSidebar } from '../state.js';

function formatDate(isoString) {
    if (!isoString) return '';
    const d = new Date(isoString);
    const now = new Date();
    const diffMs = now - d;
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return 'just now';
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr}h ago`;
    const diffDay = Math.floor(diffHr / 24);
    if (diffDay < 7) return `${diffDay}d ago`;
    return d.toLocaleDateString();
}

function statusIcon(status) {
    switch (status) {
        case 'completed': return '\u2713';
        case 'running':   return '\u25CF';
        case 'error':     return '\u2717';
        case 'interrupted': return '\u25CB';
        case 'stopped':   return '\u25A0';
        case 'imported':  return '\u2192';
        default:          return '\u25CF';
    }
}

export function Sidebar() {
    const sessions = useStore(s => s.sessions);
    const activeSessionId = useStore(s => s.activeSessionId);
    const isRunning = useStore(s => s.isRunning);
    const sessionsLoading = useStore(s => s.sessionsLoading);
    const sidebarOpen = useStore(s => s.sidebarOpen);

    function onDelete(e, sessionId) {
        e.stopPropagation();
        deleteSession(sessionId);
    }

    return html`
        <aside class="sidebar ${sidebarOpen ? 'sidebar-open' : 'sidebar-closed'}">
            <div class="sidebar-header">
                <span class="sidebar-title">Sessions</span>
                <button
                    class="btn btn-ghost btn-sm sidebar-close-btn"
                    onClick=${toggleSidebar}
                    aria-label="Close sidebar"
                >\u2715</button>
            </div>

            <button
                class="btn btn-submit sidebar-new-btn"
                onClick=${newSession}
                disabled=${isRunning}
            >
                + New Session
            </button>

            <div class="sidebar-list">
                ${sessionsLoading && html`
                    <div class="sidebar-loading">Loading...</div>
                `}
                ${!sessionsLoading && sessions.length === 0 && html`
                    <div class="sidebar-empty">No sessions yet</div>
                `}
                ${sessions.map(s => html`
                    <div
                        class="sidebar-item ${s.id === activeSessionId ? 'sidebar-item-active' : ''}"
                        onClick=${() => loadSession(s.id)}
                        key=${s.id}
                    >
                        <div class="sidebar-item-header">
                            <span class="sidebar-item-status sidebar-status-${s.status}">
                                ${statusIcon(s.status)}
                            </span>
                            <span class="sidebar-item-question">${s.question}</span>
                            <button
                                class="sidebar-item-delete"
                                onClick=${(e) => onDelete(e, s.id)}
                                aria-label="Delete session"
                            >\u2715</button>
                        </div>
                        <div class="sidebar-item-meta">
                            ${formatDate(s.created_at)} \u2022 ${s.model_id}
                        </div>
                        ${s.final_answer_preview && html`
                            <div class="sidebar-item-preview">
                                ${s.final_answer_preview.substring(0, 80)}${s.final_answer_preview.length > 80 ? '...' : ''}
                            </div>
                        `}
                    </div>
                `)}
            </div>
        </aside>
    `;
}
