import { html } from '../htm.js';
import { useState, useEffect } from 'preact/hooks';
import {
    useStore, setState, toggleSettings, toggleTheme, setRunMode,
    verifyAdminPassword, loadServerConfig, saveServerConfig,
    getClientConfig, saveClientConfig,
} from '../state.js';

const SEARCH_PROVIDER_DEFS = [
    { id: 'DDGS', label: 'DuckDuckGo', needsKey: false },
    { id: 'SERPAPI', label: 'SerpAPI', needsKey: true },
    { id: 'META_SOTA', label: 'MetaSo', needsKey: true },
];

const RUN_MODE_OPTIONS = [
    { value: 'background', label: 'Background (persistent)' },
    { value: 'auto-kill', label: 'Background (auto-kill)' },
    { value: 'live', label: 'Live (leave = stop)' },
];

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

/** Optional override input — shows placeholder with server default, empty = use server value */
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

/** Editable list of model providers (provider name, api_key, base_url) */
function ModelProvidersList({ providers, onChange }) {
    const list = providers || [];

    function updateProvider(index, field, value) {
        const next = list.map((p, i) => i === index ? { ...p, [field]: value } : p);
        onChange(next);
    }

    function removeProvider(index) {
        onChange(list.filter((_, i) => i !== index));
    }

    function addProvider() {
        onChange([...list, { provider: '', api_key: '', base_url: '' }]);
    }

    return html`
        ${list.map((p, i) => html`
            <div class="settings-provider-block" key=${i}>
                <div class="settings-provider-header">
                    <div class="settings-field" style="flex:1">
                        <label>Provider Name</label>
                        <input
                            type="text"
                            value=${p.provider}
                            placeholder="e.g. openai, deepseek, anthropic"
                            onInput=${(e) => updateProvider(i, 'provider', e.target.value)}
                            style="width: 100%"
                        />
                    </div>
                    <button
                        class="btn btn-ghost btn-sm"
                        onClick=${() => removeProvider(i)}
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
                    <label>Base URL</label>
                    <input
                        type="text"
                        value=${p.base_url || ''}
                        placeholder="Leave empty for default"
                        onInput=${(e) => updateProvider(i, 'base_url', e.target.value)}
                        style="width: 100%"
                    />
                </div>
            </div>
        `)}
        <button class="btn btn-ghost btn-sm" onClick=${addProvider}>+ Add Provider</button>
    `;
}

/** Search providers with checkboxes for enable/order and per-provider key inputs */
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
        const next = list.map(p => p.provider === id ? { ...p, key: value } : p);
        onChange(next);
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

function ClientSettings() {
    const [overrides, setOverrides] = useState(() => getClientConfig());
    const [advancedOpen, setAdvancedOpen] = useState(false);
    const theme = useStore(s => s.theme);
    const runMode = useStore(s => s.runMode);

    function updateOverrides(next) {
        setOverrides(next);
        saveClientConfig(next);
    }

    function updateOverride(section, key, value) {
        const next = { ...overrides };
        if (!next[section]) next[section] = {};
        if (value === undefined || value === '') {
            delete next[section][key];
            if (Object.keys(next[section]).length === 0) delete next[section];
        } else {
            next[section][key] = value;
        }
        updateOverrides(next);
    }

    function updateModelProviders(providers) {
        const next = { ...overrides };
        if (!next.model) next.model = {};
        if (providers && providers.length > 0) {
            next.model.providers = providers;
        } else {
            delete next.model.providers;
            if (Object.keys(next.model).length === 0) delete next.model;
        }
        updateOverrides(next);
    }

    function updateSearchProviders(providers) {
        const next = { ...overrides };
        if (!next.search) next.search = {};
        if (providers && providers.length > 0) {
            next.search.providers = providers;
        } else {
            delete next.search.providers;
            if (Object.keys(next.search).length === 0) delete next.search;
        }
        updateOverrides(next);
    }

    function clearOverrides() {
        updateOverrides({});
    }

    const g = (section, key) => overrides[section]?.[key];

    return html`
        <div class="settings-section">
            <h3>Model Providers</h3>
            <p class="settings-hint">Stored in your browser only. Provider name must match the model ID prefix (e.g. "deepseek" for "deepseek/deepseek-chat", "openai" for GPT models).</p>
            <${ModelProvidersList}
                providers=${overrides.model?.providers}
                onChange=${updateModelProviders}
            />
        </div>

        <div class="settings-section">
            <h3>Search Providers</h3>
            <p class="settings-hint">Stored in your browser only.</p>
            <${SearchProvidersList}
                providers=${overrides.search?.providers}
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

                    <button class="btn btn-ghost btn-sm" onClick=${clearOverrides} style="margin-top: var(--sp-2)">
                        Reset all overrides
                    </button>
                </div>
            `}
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

function ServerConfigEditor({ password }) {
    const [config, setConfig] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState(null);
    const [newModel, setNewModel] = useState({ id: '', name: '', description: '' });

    useEffect(() => {
        loadServerConfig(password).then(cfg => {
            setConfig(cfg);
            setLoading(false);
        }).catch(() => setLoading(false));
    }, []);

    if (loading) return html`<p class="settings-hint">Loading server config...</p>`;
    if (!config) return html`<p class="settings-hint">Failed to load server config.</p>`;

    function update(section, key, value) {
        setConfig({
            ...config,
            [section]: { ...config[section], [key]: value },
        });
    }

    function addModel() {
        if (!newModel.id || !newModel.name) return;
        setConfig({
            ...config,
            models: [...config.models, { ...newModel }],
        });
        setNewModel({ id: '', name: '', description: '' });
    }

    function removeModel(index) {
        setConfig({
            ...config,
            models: config.models.filter((_, i) => i !== index),
        });
    }

    async function onSave() {
        setSaving(true);
        setMessage(null);
        const result = await saveServerConfig(config, password);
        setSaving(false);
        if (result.success) {
            setMessage({ type: 'success', text: 'Config saved' });
        } else {
            setMessage({ type: 'error', text: result.error || 'Save failed' });
        }
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
                    class="settings-number-input"
                    value=${config.model.default_model_id}
                    onInput=${(e) => update('model', 'default_model_id', e.target.value)}
                    style="width: 100%"
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
                onChange=${(v) => setConfig({
                    ...config,
                    search: { ...config.search, providers: v || [] },
                })}
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
                onChange=${(v) => setConfig({
                    ...config,
                    other_keys: { ...config.other_keys, hf_token: v },
                })}
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

        <div class="settings-actions">
            ${message && html`
                <span class="settings-message settings-message-${message.type}">
                    ${message.text}
                </span>
            `}
            <button
                class="btn btn-submit"
                onClick=${onSave}
                disabled=${saving}
            >
                ${saving ? 'Saving...' : 'Save Server Config'}
            </button>
        </div>
    `;
}

function ServerSettings() {
    const [adminPassword, setAdminPassword] = useState(null);

    // Reset password whenever this component unmounts (tab switch / modal close)
    useEffect(() => {
        return () => setAdminPassword(null);
    }, []);

    if (!adminPassword) {
        return html`<${ServerPasswordGate} onUnlock=${(pw) => setAdminPassword(pw)} />`;
    }

    return html`<${ServerConfigEditor} password=${adminPassword} />`;
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
                    ${activeTab === 'server' && enableConfigUI && html`<${ServerSettings} />`}
                </div>
            </div>
        </div>
    `;
}
