import { html } from '../htm.js';
import { useState, useEffect } from 'preact/hooks';
import {
    useStore, toggleSettings, toggleTheme, setRunMode,
    verifyAdminPassword, loadServerConfig, saveServerConfig,
    getClientConfig, saveClientConfig,
} from '../state.js';

const SEARCH_PROVIDER_DEFS = [
    { id: 'DDGS', label: 'DuckDuckGo', needsKey: false },
    { id: 'SERPAPI', label: 'SerpAPI', needsKey: true },
    { id: 'META_SOTA', label: 'MetaSo', needsKey: true },
];

// Well-known providers that use standard endpoints (no custom base URL needed)
const KNOWN_PROVIDERS = [
    'openai', 'anthropic', 'deepseek', 'ollama', 'azure', 'groq',
    'together', 'mistral', 'cohere', 'gemini', 'google', 'bedrock',
    'vertex', 'huggingface', 'replicate', 'fireworks', 'perplexity',
];

// Providers whose default base URL is well-known — no need to fill it in
const DEFAULT_ENDPOINT_PROVIDERS = new Set([
    'openai', 'anthropic', 'deepseek', 'groq', 'mistral', 'cohere',
    'gemini', 'google', 'together', 'fireworks', 'perplexity',
]);

const RUN_MODE_OPTIONS = [
    { value: 'background', label: 'Background (persistent)' },
    { value: 'auto-kill', label: 'Background (auto-kill)' },
    { value: 'live', label: 'Live (leave = stop)' },
];

// ---------------------------------------------------------------------------
// Primitive input components
// ---------------------------------------------------------------------------

function SecretInput({ label, value, placeholder, onChange }) {
    const [visible, setVisible] = useState(false);

    return html`
        <div class="settings-field">
            <label>${label}</label>
            <div class="settings-key-input">
                <input
                    type=${visible ? 'text' : 'password'}
                    value=${value}
                    placeholder=${placeholder || 'Enter key...'}
                    onInput=${(e) => onChange(e.target.value)}
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

function NumberInput({ label, value, onChange, min, max, step }) {
    return html`
        <div class="settings-field">
            <label>${label}</label>
            <input
                type="number"
                class="settings-number-input"
                value=${value}
                min=${min}
                max=${max}
                step=${step || 1}
                onInput=${(e) => onChange(parseInt(e.target.value, 10) || 0)}
            />
        </div>
    `;
}

function OverrideNumberInput({ label, value, onChange, placeholder, min, max }) {
    return html`
        <div class="settings-field">
            <label>${label}</label>
            <input
                type="number"
                class="settings-number-input"
                value=${value ?? ''}
                placeholder=${placeholder || 'server default'}
                min=${min}
                max=${max}
                onInput=${(e) => {
                    const v = e.target.value;
                    onChange(v === '' ? undefined : parseInt(v, 10));
                }}
            />
        </div>
    `;
}

// ---------------------------------------------------------------------------
// Shared list sub-components
// ---------------------------------------------------------------------------

function ModelProvidersList({ providers, onChange }) {
    const list = providers || [];
    const listId = 'provider-names-datalist';

    function updateProvider(index, field, value) {
        onChange(list.map((p, i) => i === index ? { ...p, [field]: value } : p));
    }

    return html`
        <datalist id=${listId}>
            ${KNOWN_PROVIDERS.map(name => html`<option value=${name} key=${name} />`)}
        </datalist>
        ${list.map((p, i) => {
            const isKnown = DEFAULT_ENDPOINT_PROVIDERS.has((p.provider || '').toLowerCase());
            return html`
                <div class="settings-provider-block" key=${i}>
                    <div class="settings-provider-header">
                        <div class="settings-field" style="flex:1">
                            <label>Provider Name</label>
                            <input
                                type="text"
                                class="settings-text-input"
                                list=${listId}
                                value=${p.provider}
                                placeholder="e.g. openai, deepseek, anthropic"
                                onInput=${(e) => updateProvider(i, 'provider', e.target.value)}
                            />
                        </div>
                        <button
                            class="btn btn-ghost btn-sm"
                            onClick=${() => onChange(list.filter((_, j) => j !== i))}
                            title="Remove provider"
                            style="margin-top: 1.4em"
                        >\u2715</button>
                    </div>
                    <${SecretInput}
                        label="API Key"
                        value=${p.api_key || ''}
                        placeholder="sk-..."
                        onChange=${(v) => updateProvider(i, 'api_key', v)}
                    />
                    <div class="settings-field">
                        <label>
                            Base URL
                            ${isKnown ? html`<span class="settings-field-note">(not required for ${p.provider})</span>` : ''}
                        </label>
                        <input
                            type="text"
                            class="settings-text-input"
                            value=${p.base_url || ''}
                            placeholder=${isKnown ? `Uses ${p.provider} default endpoint` : 'https://api.example.com/v1'}
                            onInput=${(e) => updateProvider(i, 'base_url', e.target.value)}
                        />
                    </div>
                </div>
            `;
        })}
        <button
            class="btn btn-ghost btn-sm"
            onClick=${() => onChange([...list, { provider: '', api_key: '', base_url: '' }])}
        >+ Add Provider</button>
    `;
}

function SearchProvidersList({ providers, onChange }) {
    const list = providers || [];
    const activeIds = list.map(p => p.provider);

    function getTag(id) {
        const idx = activeIds.indexOf(id);
        if (idx < 0) return '';
        if (idx === 0) return ' (primary)';
        return ` (fallback #${idx})`;
    }

    function toggleProvider(id) {
        const exists = list.find(p => p.provider === id);
        if (exists) {
            const next = list.filter(p => p.provider !== id);
            onChange(next.length > 0 ? next : undefined);
        } else {
            onChange([...list, { provider: id, key: '' }]);
        }
    }

    function updateKey(id, value) {
        onChange(list.map(p => p.provider === id ? { ...p, key: value } : p));
    }

    return html`
        <div class="settings-field">
            <label>Search Providers</label>
            <p class="settings-hint">First selected provider is primary. Others are used as fallback in order.</p>
            <div class="settings-checkbox-group">
                ${SEARCH_PROVIDER_DEFS.map(def => html`
                    <label class="settings-checkbox" key=${def.id}>
                        <input
                            type="checkbox"
                            checked=${activeIds.includes(def.id)}
                            onChange=${() => toggleProvider(def.id)}
                        />
                        ${def.label}${getTag(def.id)}
                    </label>
                `)}
            </div>
        </div>
        ${SEARCH_PROVIDER_DEFS.filter(def => def.needsKey && activeIds.includes(def.id)).map(def => {
            const entry = list.find(p => p.provider === def.id);
            return html`
                <${SecretInput}
                    key=${'search-' + def.id}
                    label=${def.label + ' API Key'}
                    value=${entry?.key || ''}
                    onChange=${(v) => updateKey(def.id, v)}
                />
            `;
        })}
    `;
}

// ---------------------------------------------------------------------------
// Pure form components — no internal save state, no footer rendering
// ---------------------------------------------------------------------------

function ClientSettingsForm({ draft, onChange }) {
    const [advancedOpen, setAdvancedOpen] = useState(false);
    const theme = useStore(s => s.theme);
    const runMode = useStore(s => s.runMode);

    function updateOverride(section, key, value) {
        const next = { ...draft };
        if (!next[section]) next[section] = {};
        if (value === undefined || value === '') {
            delete next[section][key];
            if (Object.keys(next[section]).length === 0) delete next[section];
        } else {
            next[section][key] = value;
        }
        onChange(next);
    }

    function updateModelProviders(providers) {
        const next = { ...draft };
        if (!next.model) next.model = {};
        if (providers && providers.length > 0) {
            next.model.providers = providers;
        } else {
            delete next.model.providers;
            if (Object.keys(next.model).length === 0) delete next.model;
        }
        onChange(next);
    }

    function updateSearchProviders(providers) {
        const next = { ...draft };
        if (!next.search) next.search = {};
        if (providers && providers.length > 0) {
            next.search.providers = providers;
        } else {
            delete next.search.providers;
            if (Object.keys(next.search).length === 0) delete next.search;
        }
        onChange(next);
    }

    const g = (section, key) => draft[section]?.[key];

    return html`
        <div class="settings-section">
            <h3>Model Providers</h3>
            <p class="settings-hint">Stored in your browser only. Provider name must match the model ID prefix (e.g. "deepseek" for "deepseek/deepseek-chat", "openai" for GPT models).</p>
            <${ModelProvidersList}
                providers=${draft.model?.providers}
                onChange=${updateModelProviders}
            />
        </div>

        <div class="settings-section">
            <h3>Search Providers</h3>
            <p class="settings-hint">Stored in your browser only.</p>
            <${SearchProvidersList}
                providers=${draft.search?.providers}
                onChange=${updateSearchProviders}
            />
        </div>

        <div class="settings-section">
            <h3>Other Keys</h3>
            <${SecretInput}
                label="HuggingFace Token"
                value=${g('other_keys', 'hf_token') || ''}
                placeholder="hf_..."
                onChange=${(v) => updateOverride('other_keys', 'hf_token', v)}
            />
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
                <select value=${runMode} onChange=${(e) => setRunMode(e.target.value)}>
                    ${RUN_MODE_OPTIONS.map(opt => html`
                        <option value=${opt.value}>${opt.label}</option>
                    `)}
                </select>
            </div>
        </div>

        <div class="settings-section">
            <button
                class="btn btn-ghost settings-advanced-toggle"
                onClick=${() => setAdvancedOpen(!advancedOpen)}
            >
                ${advancedOpen ? '\u25BC' : '\u25B6'} Advanced Overrides
            </button>
            <p class="settings-hint">Override server defaults for this browser. Leave empty to use server values.</p>

            ${advancedOpen && html`
                <div class="settings-advanced">
                    <h4>Agent</h4>
                    <${OverrideNumberInput} label="Search Agent Max Steps"
                        value=${g('agent', 'search_agent_max_steps')}
                        onChange=${(v) => updateOverride('agent', 'search_agent_max_steps', v)}
                        min=${1} max=${100} />
                    <${OverrideNumberInput} label="Manager Agent Max Steps"
                        value=${g('agent', 'manager_agent_max_steps')}
                        onChange=${(v) => updateOverride('agent', 'manager_agent_max_steps', v)}
                        min=${1} max=${100} />
                    <${OverrideNumberInput} label="Planning Interval"
                        value=${g('agent', 'planning_interval')}
                        onChange=${(v) => updateOverride('agent', 'planning_interval', v)}
                        min=${1} max=${50} />

                    <h4>Model</h4>
                    <${OverrideNumberInput} label="Max Completion Tokens"
                        value=${g('model', 'max_completion_tokens')}
                        onChange=${(v) => updateOverride('model', 'max_completion_tokens', v)}
                        min=${256} max=${65536} />
                    <div class="settings-field">
                        <label>Reasoning Effort (o1 only)</label>
                        <select
                            value=${g('model', 'reasoning_effort') || ''}
                            onChange=${(e) => updateOverride('model', 'reasoning_effort', e.target.value || undefined)}
                        >
                            <option value="">server default</option>
                            <option value="low">Low</option>
                            <option value="medium">Medium</option>
                            <option value="high">High</option>
                        </select>
                    </div>

                    <h4>Search</h4>
                    <${OverrideNumberInput} label="Max Results"
                        value=${g('search', 'max_results')}
                        onChange=${(v) => updateOverride('search', 'max_results', v)}
                        min=${1} max=${50} />

                    <h4>Browser</h4>
                    <${OverrideNumberInput} label="Viewport Size (chars)"
                        value=${g('browser', 'viewport_size')}
                        onChange=${(v) => updateOverride('browser', 'viewport_size', v)}
                        min=${1024} max=${20480} />
                    <${OverrideNumberInput} label="Request Timeout (seconds)"
                        value=${g('browser', 'request_timeout')}
                        onChange=${(v) => updateOverride('browser', 'request_timeout', v)}
                        min=${10} max=${600} />

                    <h4>Limits</h4>
                    <${OverrideNumberInput} label="Text Limit (chars)"
                        value=${g('limits', 'text_limit')}
                        onChange=${(v) => updateOverride('limits', 'text_limit', v)}
                        min=${1000} max=${500000} />
                    <${OverrideNumberInput} label="Max Field Length (chars)"
                        value=${g('limits', 'max_field_length')}
                        onChange=${(v) => updateOverride('limits', 'max_field_length', v)}
                        min=${1000} max=${200000} />

                    <button class="btn btn-ghost btn-sm" onClick=${() => onChange({})} style="margin-top: var(--sp-2)">
                        Reset all overrides
                    </button>
                </div>
            `}
        </div>
    `;
}

function ServerConfigForm({ config, onChange }) {
    const [newModel, setNewModel] = useState({ id: '', name: '', description: '' });

    function update(section, key, value) {
        onChange({ ...config, [section]: { ...config[section], [key]: value } });
    }

    function addModel() {
        if (!newModel.id || !newModel.name) return;
        onChange({ ...config, models: [...config.models, { ...newModel }] });
        setNewModel({ id: '', name: '', description: '' });
    }

    function removeModel(index) {
        onChange({ ...config, models: config.models.filter((_, i) => i !== index) });
    }

    return html`
        <div class="settings-section">
            <h3>Agent</h3>
            <${NumberInput} label="Search Agent Max Steps"
                value=${config.agent.search_agent_max_steps}
                onChange=${(v) => update('agent', 'search_agent_max_steps', v)}
                min=${1} max=${100} />
            <${NumberInput} label="Manager Agent Max Steps"
                value=${config.agent.manager_agent_max_steps}
                onChange=${(v) => update('agent', 'manager_agent_max_steps', v)}
                min=${1} max=${100} />
            <${NumberInput} label="Planning Interval"
                value=${config.agent.planning_interval}
                onChange=${(v) => update('agent', 'planning_interval', v)}
                min=${1} max=${50} />
            <${NumberInput} label="Verbosity Level"
                value=${config.agent.verbosity_level}
                onChange=${(v) => update('agent', 'verbosity_level', v)}
                min=${0} max=${5} />
        </div>

        <div class="settings-section">
            <h3>Model</h3>
            <div class="settings-field">
                <label>Default Model ID</label>
                <input
                    type="text"
                    class="settings-text-input"
                    value=${config.model.default_model_id}
                    onInput=${(e) => update('model', 'default_model_id', e.target.value)}
                />
            </div>
            <${NumberInput} label="Max Completion Tokens"
                value=${config.model.max_completion_tokens}
                onChange=${(v) => update('model', 'max_completion_tokens', v)}
                min=${256} max=${65536} />
            <div class="settings-field">
                <label>Reasoning Effort (o1 only)</label>
                <select
                    value=${config.model.reasoning_effort}
                    onChange=${(e) => update('model', 'reasoning_effort', e.target.value)}
                >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                </select>
            </div>
        </div>

        <div class="settings-section">
            <h3>Model Providers</h3>
            <p class="settings-hint">Shared provider keys. Masked values shown — enter new value to replace.</p>
            <${ModelProvidersList}
                providers=${config.model?.providers || []}
                onChange=${(v) => update('model', 'providers', v)}
            />
        </div>

        <div class="settings-section">
            <h3>Search</h3>
            <${SearchProvidersList}
                providers=${config.search?.providers || []}
                onChange=${(v) => onChange({ ...config, search: { ...config.search, providers: v || [] } })}
            />
            <${NumberInput} label="Max Results"
                value=${config.search.max_results}
                onChange=${(v) => update('search', 'max_results', v)}
                min=${1} max=${50} />
        </div>

        <div class="settings-section">
            <h3>Other Keys</h3>
            <p class="settings-hint">Masked values shown — enter new value to replace.</p>
            <${SecretInput}
                label="HuggingFace Token"
                value=${config.other_keys?.hf_token || ''}
                placeholder="hf_..."
                onChange=${(v) => onChange({ ...config, other_keys: { ...config.other_keys, hf_token: v } })}
            />
        </div>

        <div class="settings-section">
            <h3>Browser</h3>
            <${NumberInput} label="Viewport Size (chars)"
                value=${config.browser.viewport_size}
                onChange=${(v) => update('browser', 'viewport_size', v)}
                min=${1024} max=${20480} />
            <${NumberInput} label="Request Timeout (seconds)"
                value=${config.browser.request_timeout}
                onChange=${(v) => update('browser', 'request_timeout', v)}
                min=${10} max=${600} />
        </div>

        <div class="settings-section">
            <h3>Limits</h3>
            <${NumberInput} label="Text Limit (chars)"
                value=${config.limits.text_limit}
                onChange=${(v) => update('limits', 'text_limit', v)}
                min=${1000} max=${500000} />
            <${NumberInput} label="Max Field Length (chars)"
                value=${config.limits.max_field_length}
                onChange=${(v) => update('limits', 'max_field_length', v)}
                min=${1000} max=${200000} />
        </div>

        <div class="settings-section">
            <h3>Available Models</h3>
            <div class="settings-models-list">
                ${config.models.map((m, i) => html`
                    <div class="settings-model-item" key=${m.id}>
                        <span class="settings-model-id">${m.id}</span>
                        <span class="settings-model-name">${m.name}</span>
                        <button
                            class="btn btn-ghost btn-sm"
                            onClick=${() => removeModel(i)}
                            title="Remove model"
                        >\u2715</button>
                    </div>
                `)}
            </div>
            <div class="settings-add-model">
                <input
                    type="text"
                    placeholder="Model ID"
                    value=${newModel.id}
                    onInput=${(e) => setNewModel({ ...newModel, id: e.target.value })}
                />
                <input
                    type="text"
                    placeholder="Display Name"
                    value=${newModel.name}
                    onInput=${(e) => setNewModel({ ...newModel, name: e.target.value })}
                />
                <input
                    type="text"
                    placeholder="Description"
                    value=${newModel.description}
                    onInput=${(e) => setNewModel({ ...newModel, description: e.target.value })}
                />
                <button class="btn btn-ghost btn-sm" onClick=${addModel}>+ Add</button>
            </div>
        </div>
    `;
}

function ServerPasswordGate({ onUnlock }) {
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [verifying, setVerifying] = useState(false);

    async function onSubmit(e) {
        e.preventDefault();
        if (!password) return;
        setVerifying(true);
        setError('');
        const valid = await verifyAdminPassword(password);
        setVerifying(false);
        if (valid) {
            onUnlock(password);
        } else {
            setError('Invalid admin password');
        }
    }

    return html`
        <div class="settings-password-gate">
            <p class="settings-hint">Enter admin password to access server configuration.</p>
            <form onSubmit=${onSubmit}>
                <div class="settings-field">
                    <div class="settings-key-input">
                        <input
                            type="password"
                            value=${password}
                            placeholder="Admin password..."
                            onInput=${(e) => setPassword(e.target.value)}
                            autocomplete="off"
                            autofocus
                        />
                        <button
                            type="submit"
                            class="btn btn-submit btn-sm"
                            disabled=${verifying || !password}
                        >${verifying ? '...' : 'Unlock'}</button>
                    </div>
                </div>
                ${error && html`<p class="settings-message settings-message-error">${error}</p>`}
            </form>
        </div>
    `;
}

// ---------------------------------------------------------------------------
// SettingsModal — owns all state, renders fixed footer with Save/Cancel
// ---------------------------------------------------------------------------

export function SettingsModal() {
    const settingsOpen = useStore(s => s.settingsOpen);
    const enableConfigUI = useStore(s => s.enableConfigUI);
    const [activeTab, setActiveTab] = useState('client');

    // --- Client state ---
    const [clientSaved, setClientSaved] = useState(() => getClientConfig());
    const [clientDraft, setClientDraft] = useState(() => getClientConfig());
    const clientDirty = JSON.stringify(clientDraft) !== JSON.stringify(clientSaved);

    function onClientSave() {
        saveClientConfig(clientDraft);
        setClientSaved(clientDraft);
    }

    function onClientCancel() {
        setClientDraft(clientSaved);
    }

    // --- Server state ---
    const [adminPassword, setAdminPassword] = useState(null);
    const [serverConfig, setServerConfig] = useState(null);
    const [serverSaved, setServerSaved] = useState(null);
    const [serverLoading, setServerLoading] = useState(false);
    const [serverSaving, setServerSaving] = useState(false);
    const [serverMessage, setServerMessage] = useState(null);

    const serverDirty = serverConfig !== null &&
        JSON.stringify(serverConfig) !== JSON.stringify(serverSaved);

    function onAdminUnlock(password) {
        setAdminPassword(password);
        setServerLoading(true);
        setServerConfig(null);
        setServerSaved(null);
        loadServerConfig(password).then(cfg => {
            setServerConfig(cfg);
            setServerSaved(cfg);
            setServerLoading(false);
        }).catch(() => setServerLoading(false));
    }

    async function onServerSave() {
        setServerSaving(true);
        setServerMessage(null);
        const result = await saveServerConfig(serverConfig, adminPassword);
        setServerSaving(false);
        if (result.success) {
            setServerSaved(serverConfig);
            setServerMessage({ type: 'success', text: 'Config saved' });
        } else {
            setServerMessage({ type: 'error', text: result.error || 'Save failed' });
        }
    }

    function onServerCancel() {
        setServerConfig(serverSaved);
        setServerMessage(null);
    }

    // Reset server state when modal closes or tab changes away
    function onTabChange(tab) {
        if (tab !== 'server') {
            setAdminPassword(null);
            setServerConfig(null);
            setServerSaved(null);
            setServerMessage(null);
        }
        setActiveTab(tab);
    }

    if (!settingsOpen) return null;

    function onOverlayClick(e) {
        if (e.target.classList.contains('settings-modal-overlay')) {
            toggleSettings();
        }
    }

    // --- Footer content per tab ---
    let footer = null;
    if (activeTab === 'client') {
        footer = html`
            <button class="btn btn-ghost btn-sm" onClick=${onClientCancel} disabled=${!clientDirty}>
                Cancel
            </button>
            <button class="btn btn-submit" onClick=${onClientSave} disabled=${!clientDirty}>
                Save
            </button>
        `;
    } else if (activeTab === 'server' && adminPassword && serverConfig) {
        footer = html`
            ${serverMessage && html`
                <span class="settings-message settings-message-${serverMessage.type}">
                    ${serverMessage.text}
                </span>
            `}
            <button class="btn btn-ghost btn-sm" onClick=${onServerCancel} disabled=${!serverDirty}>
                Cancel
            </button>
            <button class="btn btn-submit" onClick=${onServerSave} disabled=${serverSaving || !serverDirty}>
                ${serverSaving ? 'Saving...' : 'Save'}
            </button>
        `;
    }

    return html`
        <div class="settings-modal-overlay" onClick=${onOverlayClick}>
            <div class="settings-modal">
                <div class="settings-modal-header">
                    <h2>Settings</h2>
                    <button class="btn btn-ghost" onClick=${toggleSettings}>\u2715</button>
                </div>

                <div class="settings-tabs">
                    <button
                        class="settings-tab ${activeTab === 'client' ? 'settings-tab-active' : ''}"
                        onClick=${() => onTabChange('client')}
                    >Client</button>
                    ${enableConfigUI && html`
                        <button
                            class="settings-tab ${activeTab === 'server' ? 'settings-tab-active' : ''}"
                            onClick=${() => onTabChange('server')}
                        >Server</button>
                    `}
                </div>

                <div class="settings-modal-body">
                    ${activeTab === 'client' && html`
                        <${ClientSettingsForm} draft=${clientDraft} onChange=${setClientDraft} />
                    `}
                    ${activeTab === 'server' && enableConfigUI && html`
                        ${!adminPassword && html`<${ServerPasswordGate} onUnlock=${onAdminUnlock} />`}
                        ${adminPassword && serverLoading && html`<p class="settings-hint">Loading server config...</p>`}
                        ${adminPassword && !serverLoading && !serverConfig && html`<p class="settings-hint">Failed to load server config.</p>`}
                        ${adminPassword && serverConfig && html`
                            <${ServerConfigForm} config=${serverConfig} onChange=${setServerConfig} />
                        `}
                    `}
                </div>

                ${footer && html`<div class="settings-modal-footer">${footer}</div>`}
            </div>
        </div>
    `;
}
