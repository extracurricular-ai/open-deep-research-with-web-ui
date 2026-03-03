import { html } from '../htm.js';
import { useState, useEffect } from 'preact/hooks';
import {
    useStore, setState, toggleSettings, toggleTheme, setRunMode,
} from '../state.js';

const API_KEY_FIELDS = [
    { key: 'openai', label: 'OpenAI API Key', placeholder: 'sk-...' },
    { key: 'deepseek', label: 'DeepSeek API Key', placeholder: 'sk-...' },
    { key: 'serpapi', label: 'SerpAPI Key', placeholder: '' },
    { key: 'meta_sota', label: 'MetaSo API Key', placeholder: '' },
    { key: 'hf_token', label: 'HuggingFace Token', placeholder: 'hf_...' },
];

const RUN_MODE_OPTIONS = [
    { value: 'background', label: 'Background (persistent)' },
    { value: 'auto-kill', label: 'Background (auto-kill)' },
    { value: 'live', label: 'Live (leave = stop)' },
];

function getClientApiKeys() {
    const keys = {};
    for (const f of API_KEY_FIELDS) {
        keys[f.key] = localStorage.getItem(`odr-apikey-${f.key}`) || '';
    }
    return keys;
}

function ApiKeyInput({ field, value, onChange }) {
    const [visible, setVisible] = useState(false);

    return html`
        <div class="settings-field">
            <label>${field.label}</label>
            <div class="settings-key-input">
                <input
                    type=${visible ? 'text' : 'password'}
                    value=${value}
                    placeholder=${field.placeholder || 'Enter key...'}
                    onInput=${(e) => onChange(field.key, e.target.value)}
                    autocomplete="off"
                    spellcheck="false"
                />
                <button
                    type="button"
                    class="btn btn-ghost btn-sm settings-toggle-vis"
                    onClick=${() => setVisible(!visible)}
                    aria-label=${visible ? 'Hide' : 'Show'}
                >${visible ? '\u25C9' : '\u25CE'}</button>
            </div>
        </div>
    `;
}

function ClientSettings() {
    const [keys, setKeys] = useState(getClientApiKeys);
    const theme = useStore(s => s.theme);
    const runMode = useStore(s => s.runMode);

    function onKeyChange(key, value) {
        const next = { ...keys, [key]: value };
        setKeys(next);
        if (value) {
            localStorage.setItem(`odr-apikey-${key}`, value);
        } else {
            localStorage.removeItem(`odr-apikey-${key}`);
        }
    }

    function clearAllKeys() {
        const empty = {};
        for (const f of API_KEY_FIELDS) {
            empty[f.key] = '';
            localStorage.removeItem(`odr-apikey-${f.key}`);
        }
        setKeys(empty);
    }

    return html`
        <div class="settings-section">
            <h3>API Keys</h3>
            <p class="settings-hint">Stored in your browser only. Never sent to the server for storage.</p>
            ${API_KEY_FIELDS.map(f => html`
                <${ApiKeyInput}
                    key=${f.key}
                    field=${f}
                    value=${keys[f.key]}
                    onChange=${onKeyChange}
                />
            `)}
            <button class="btn btn-ghost btn-sm" onClick=${clearAllKeys}>
                Clear all keys
            </button>
        </div>

        <div class="settings-section">
            <h3>Preferences</h3>
            <div class="settings-field">
                <label>Theme</label>
                <select value=${theme} onChange=${() => toggleTheme()}>
                    <option value="dark">Dark</option>
                    <option value="light">Light</option>
                </select>
            </div>
            <div class="settings-field">
                <label>Default Run Mode</label>
                <select
                    value=${runMode}
                    onChange=${(e) => setRunMode(e.target.value)}
                >
                    ${RUN_MODE_OPTIONS.map(opt => html`
                        <option value=${opt.value}>${opt.label}</option>
                    `)}
                </select>
            </div>
        </div>
    `;
}

export function SettingsModal() {
    const settingsOpen = useStore(s => s.settingsOpen);
    const enableConfigUI = useStore(s => s.enableConfigUI);
    const [activeTab, setActiveTab] = useState('client');

    if (!settingsOpen) return null;

    function onOverlayClick(e) {
        if (e.target.classList.contains('settings-modal-overlay')) {
            toggleSettings();
        }
    }

    return html`
        <div class="settings-modal-overlay" onClick=${onOverlayClick}>
            <div class="settings-modal">
                <div class="settings-modal-header">
                    <h2>Settings</h2>
                    <button class="btn btn-ghost" onClick=${toggleSettings}>
                        \u2715
                    </button>
                </div>

                <div class="settings-tabs">
                    <button
                        class="settings-tab ${activeTab === 'client' ? 'settings-tab-active' : ''}"
                        onClick=${() => setActiveTab('client')}
                    >Client</button>
                    ${enableConfigUI && html`
                        <button
                            class="settings-tab ${activeTab === 'server' ? 'settings-tab-active' : ''}"
                            onClick=${() => setActiveTab('server')}
                        >Server</button>
                    `}
                </div>

                <div class="settings-modal-body">
                    ${activeTab === 'client' && html`<${ClientSettings} />`}
                    ${activeTab === 'server' && enableConfigUI && html`
                        <div class="settings-section">
                            <p class="settings-hint">Server configuration — coming in next update.</p>
                        </div>
                    `}
                </div>
            </div>
        </div>
    `;
}
