import { html } from '../htm.js';
import {
    useStore, setState,
    startStream, stopStream, resetState, newSession, setRunMode,
} from '../state.js';
import { StatusBar } from './StatusBar.js';

export function InputPanel() {
    const store = useStore();

    function onSubmit(e) {
        e.preventDefault();
        startStream();
    }

    function onClear() {
        resetState();
        setState({ question: '' });
    }

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
                    <label for="runMode">Run Mode</label>
                    <select
                        id="runMode"
                        value=${store.runMode}
                        onChange=${(e) => setRunMode(e.target.value)}
                    >
                        <option value="background">Background (reconnectable)</option>
                        <option value="auto-kill">Auto-kill on disconnect</option>
                        <option value="session-bound">Session-bound (stops on switch)</option>
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
                    <button
                        type="submit"
                        class="btn btn-submit"
                        disabled=${store.isRunning}
                    >
                        Run Agent <kbd>Ctrl+Enter</kbd>
                    </button>
                    ${store.isRunning && html`
                        <button
                            type="button"
                            class="btn btn-stop"
                            onClick=${stopStream}
                        >
                            Stop <kbd>Esc</kbd>
                        </button>
                    `}
                    <button type="button" class="btn btn-ghost" onClick=${onClear}>Clear</button>
                </div>
            </form>
            <${StatusBar} />
        </div>
    `;
}
