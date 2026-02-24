import { useEffect, useRef } from 'preact/hooks';
import { html } from '../htm.js';
import { useStore } from '../state.js';
import { formatElapsedTime } from '../utils.js';

export function StatusBar() {
    const status = useStore(s => s.status);
    const isRunning = useStore(s => s.isRunning);
    const totalStartTime = useStore(s => s.totalStartTime);
    const elapsedRef = useRef(null);

    useEffect(() => {
        if (!isRunning || !totalStartTime) return;

        const interval = setInterval(() => {
            if (elapsedRef.current && totalStartTime) {
                const elapsed = Math.round((Date.now() - totalStartTime) / 1000);
                elapsedRef.current.textContent = formatElapsedTime(elapsed);
            }
        }, 1000);

        return () => clearInterval(interval);
    }, [isRunning, totalStartTime]);

    if (!status.message && !status.type) return null;

    return html`
        <div class="status-bar status-${status.type}">
            ${status.type === 'loading' && html`<span class="spinner" />`}
            <span class="status-dot status-dot-${status.type}" />
            <span class="status-text">${status.message}</span>
            <span class="status-elapsed" ref=${elapsedRef} />
        </div>
    `;
}
