import { html } from '../htm.js';
import { useState, useEffect, useRef } from 'preact/hooks';
import {
    useStore, setState,
    startStream, stopStream, newSession, setRunMode,
} from '../state.js';
import { StatusBar } from './StatusBar.js';

const MODE_LABELS = {
    'background': 'BG',
    'auto-kill': 'Auto-kill',
    'live': 'Live',
};

const MODE_OPTIONS = [
    { value: 'background', label: 'Background (persistent)', desc: 'Survives browser close' },
    { value: 'auto-kill', label: 'Background (auto-kill)', desc: 'Dies when browser closes' },
    { value: 'live', label: 'Live (leave = stop)', desc: 'Leaving stops agent' },
];

function RunSplitButton({ runMode, disabled }) {
    const [open, setOpen] = useState(false);
    const ref = useRef(null);

    // Close dropdown on outside click
    useEffect(() => {
        if (!open) return;
        function onClick(e) {
            if (ref.current && !ref.current.contains(e.target)) setOpen(false);
        }
        document.addEventListener('mousedown', onClick);
        return () => document.removeEventListener('mousedown', onClick);
    }, [open]);

    function selectMode(mode) {
        setRunMode(mode);
        setOpen(false);
    }

    return html`
        <div class="split-btn" ref=${ref}>
            <button
                type="submit"
                class="btn btn-submit split-btn-main"
                disabled=${disabled}
            >
                Run <span class="split-btn-mode">${MODE_LABELS[runMode]}</span> <kbd>Ctrl+Enter</kbd>
            </button>
            <button
                type="button"
                class="btn btn-submit split-btn-chevron"
                onClick=${(e) => { e.preventDefault(); setOpen(!open); }}
                aria-label="Select run mode"
            >\u25BE</button>
            ${open && html`
                <div class="split-btn-menu">
                    ${MODE_OPTIONS.map(opt => html`
                        <button
                            type="button"
                            class="split-btn-option ${opt.value === runMode ? 'split-btn-option-active' : ''}"
                            onClick=${() => selectMode(opt.value)}
                            key=${opt.value}
                        >
                            <span class="split-btn-option-label">${opt.label}</span>
                            <span class="split-btn-option-desc">${opt.desc}</span>
                        </button>
                    `)}
                </div>
            `}
        </div>
    `;
}

export function InputPanel() {
    const store = useStore();

    function onSubmit(e) {
        e.preventDefault();
        startStream();
    }

    // isRunning only locks UI in live mode. In background/auto-kill, user can always start new.
    const uiLocked = store.isRunning && store.runMode === 'live';

    return html`
        <div class="panel input-panel">
            <h2>Input</h2>
            ${store.viewingHistory && html`
                <div class="history-badge">
                    Viewing saved session
                    <button class="btn btn-ghost btn-sm" onClick=${newSession}>New Session</button>
                </div>
            `}
            <form onSubmit=${onSubmit}>
                <div class="form-group">
                    <label for="modelSelect">Model</label>
                    <select
                        id="modelSelect"
                        value=${store.selectedModel}
                        onChange=${(e) => setState({ selectedModel: e.target.value })}
                    >
                        ${store.models.map(m => html`
                            <option value=${m.id} title=${m.description || ''}>${m.name}</option>
                        `)}
                    </select>
                </div>

                <div class="form-group">
                    <label for="question">Question</label>
                    <textarea
                        id="question"
                        placeholder="Enter your research question..."
                        value=${store.question}
                        onInput=${(e) => setState({ question: e.target.value })}
                        required
                    />
                </div>

                <div class="button-group">
                    <${RunSplitButton} runMode=${store.runMode} disabled=${uiLocked} />
                    ${(store.isRunning || store.viewingLiveSession) && html`
                        <button
                            type="button"
                            class="btn btn-stop"
                            onClick=${stopStream}
                        >
                            Stop <kbd>Esc</kbd>
                        </button>
                    `}
                </div>
            </form>
            <${StatusBar} />
        </div>
    `;
}
