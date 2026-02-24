import { html } from '../htm.js';
import {
    useStore, setState,
    startStream, stopStream, resetState,
} from '../state.js';
import { StatusBar } from './StatusBar.js';
import { HistoryPanel } from './HistoryPanel.js';

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

    function onToggleHistory() {
        setState({ historyOpen: !store.historyOpen });
    }

    return html`
        <div class="panel input-panel">
            <h2>Input</h2>
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
                    <button type="button" class="btn btn-ghost" onClick=${onToggleHistory}>History</button>
                </div>
            </form>

            ${store.historyOpen && html`<${HistoryPanel} />`}
            <${StatusBar} />
        </div>
    `;
}
