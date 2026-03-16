// MOI Agent — Dashboard JS

let ws = null;
let currentTab = 'chat';

// --- WebSocket ---
function connectWS() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${proto}//${location.host}/ws`);
    ws.onopen = () => console.log('WS connected');
    ws.onmessage = (evt) => {
        const data = JSON.parse(evt.data);
        switch (data.event) {
            case 'chat': addChatBubble(data.role, data.content, data.model); break;
            case 'task': updateTask(data); break;
            case 'approval': showApproval(data.action); break;
        }
    };
    ws.onclose = () => setTimeout(connectWS, 2000);
}

// --- Chat ---
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatMessages = document.getElementById('chat-messages');

chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const msg = chatInput.value.trim();
    if (!msg) return;
    addChatBubble('user', msg);
    chatInput.value = '';
    chatInput.focus();

    // Show loading indicator
    const loadingId = showLoading();

    try {
        const resp = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: msg }),
        });
        removeLoading(loadingId);
        const data = await resp.json();
        if (data.type === 'chat') {
            addChatBubble('assistant', data.content);
        } else if (data.type === 'task') {
            addChatBubble('system', `Task submitted: ${data.task_id}`);
        }
    } catch (err) {
        removeLoading(loadingId);
        addChatBubble('system', `Error: ${err.message}`);
    }
});

function showLoading() {
    const id = 'loading-' + Date.now();
    const div = document.createElement('div');
    div.id = id;
    div.className = 'chat-bubble';
    div.innerHTML = `
        <div class="max-w-3xl">
            <div class="text-xs text-gray-500 mb-1">MOI</div>
            <div class="rounded-xl border bg-gray-800 border-gray-700 p-4 text-sm text-gray-400 flex items-center gap-3">
                <div class="flex gap-1">
                    <span class="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style="animation-delay: 0s"></span>
                    <span class="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style="animation-delay: 0.15s"></span>
                    <span class="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style="animation-delay: 0.3s"></span>
                </div>
                En action...
            </div>
        </div>`;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return id;
}

function removeLoading(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function addChatBubble(role, content, model = '') {
    const placeholder = chatMessages.querySelector('.text-center');
    if (placeholder) placeholder.remove();

    const div = document.createElement('div');
    div.className = 'chat-bubble';
    const isUser = role === 'user';
    const isSystem = role === 'system';
    let bg = isUser ? 'bg-blue-600/20 border-blue-500/30' :
             isSystem ? 'bg-yellow-600/20 border-yellow-500/30' :
             'bg-gray-800 border-gray-700';
    // Model badges with distinct colors
    const modelColors = {
        'claude': 'bg-orange-600/30 text-orange-300 border border-orange-500/30',
        'qwen': 'bg-cyan-600/30 text-cyan-300 border border-cyan-500/30',
        'gemini': 'bg-blue-600/30 text-blue-300 border border-blue-500/30',
    };
    const modelLabels = {
        'claude': 'Claude 4.6',
        'qwen': 'Qwen 3 235B',
        'gemini': 'Gemini',
    };
    const badgeColor = modelColors[model] || 'bg-gray-700 text-gray-400';
    const badgeLabel = modelLabels[model] || model;
    const badge = model ? `<span class="text-xs px-2 py-0.5 rounded-full ${badgeColor} ml-2">${badgeLabel}</span>` : '';

    div.innerHTML = `
        <div class="max-w-3xl ${isUser ? 'ml-auto' : ''}">
            <div class="text-xs text-gray-500 mb-1 ${isUser ? 'text-right' : ''}">
                ${isUser ? 'You' : isSystem ? 'System' : 'MOI'}${badge}
            </div>
            <div class="rounded-xl border ${bg} p-4 text-sm whitespace-pre-wrap">${escapeHtml(content)}</div>
        </div>`;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// --- Task ---
function updateTask(data) {
    const statusEl = document.getElementById('agent-status');
    const taskEl = document.getElementById('active-task');
    if (data.status === 'running') {
        statusEl.textContent = 'Running'; statusEl.className = 'text-sm text-yellow-400';
        taskEl.textContent = data.instruction;
    } else if (data.status === 'done') {
        statusEl.textContent = 'Idle'; statusEl.className = 'text-sm text-green-400';
        taskEl.textContent = 'None';
        if (data.result) addChatBubble('assistant', `Task ${data.id} done:\n${data.result}`);
    } else if (data.status === 'failed') {
        statusEl.textContent = 'Idle'; statusEl.className = 'text-sm text-green-400';
        taskEl.textContent = 'None';
        addChatBubble('system', `Task ${data.id} failed: ${data.result}`);
    } else if (data.status === 'waiting_approval') {
        statusEl.textContent = 'Waiting approval'; statusEl.className = 'text-sm text-orange-400';
    }
}

// --- Approval ---
function showApproval(action) {
    document.getElementById('approval-banner').classList.remove('hidden');
    document.getElementById('approval-action').textContent = action;
}
async function approve(yes) {
    await fetch('/approve', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approved: yes }),
    });
    document.getElementById('approval-banner').classList.add('hidden');
}

// --- Tabs ---
const allTabs = ['chat', 'logs', 'cron', 'skills'];
function switchTab(tab) {
    currentTab = tab;
    allTabs.forEach(t => {
        const panel = document.getElementById(`panel-${t}`);
        const btn = document.getElementById(`tab-${t}`);
        if (t === tab) {
            panel.classList.remove('hidden'); panel.classList.add('flex');
            btn.className = 'w-full text-left px-3 py-2 rounded-lg text-sm bg-gray-800 text-white';
        } else {
            panel.classList.add('hidden'); panel.classList.remove('flex');
            btn.className = 'w-full text-left px-3 py-2 rounded-lg text-sm text-gray-400 hover:bg-gray-800';
        }
    });
    if (tab === 'logs') loadLogs();
    if (tab === 'cron') loadCron();
    if (tab === 'skills') loadSkills();
}

// --- Logs ---
async function loadLogs() {
    try {
        const resp = await fetch('/logs');
        const logs = await resp.json();
        const el = document.getElementById('log-container');
        el.innerHTML = logs.map(l => {
            const c = l.level === 'ERROR' ? 'text-red-400' :
                      l.level === 'WARNING' ? 'text-yellow-400' :
                      l.level === 'DEBUG' ? 'text-gray-600' : 'text-gray-300';
            return `<div class="${c}">${escapeHtml(l.msg)}</div>`;
        }).join('');
        el.scrollTop = el.scrollHeight;
    } catch(e) {}
}
function clearLogs() { document.getElementById('log-container').innerHTML = ''; }

// --- Cron ---
document.getElementById('cron-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('cron-name').value.trim();
    const instruction = document.getElementById('cron-instruction').value.trim();
    const interval = parseInt(document.getElementById('cron-interval').value) || 60;
    if (!name || !instruction) return;
    await fetch('/cron', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, instruction, interval_minutes: interval }),
    });
    document.getElementById('cron-name').value = '';
    document.getElementById('cron-instruction').value = '';
    loadCron();
});

async function loadCron() {
    const resp = await fetch('/cron');
    const jobs = await resp.json();
    const el = document.getElementById('cron-list');
    if (!jobs.length) { el.innerHTML = '<div class="text-gray-500 text-sm">No cron jobs. Add one above.</div>'; return; }
    el.innerHTML = jobs.map(j => `
        <div class="bg-gray-800 rounded-lg p-3 flex items-center justify-between">
            <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                    <span class="w-2 h-2 rounded-full ${j.enabled ? 'bg-green-500' : 'bg-gray-600'}"></span>
                    <span class="font-medium text-sm">${escapeHtml(j.name)}</span>
                    <span class="text-xs text-gray-500">every ${j.interval_minutes}m</span>
                    <span class="text-xs text-gray-600">(ran ${j.run_count}x)</span>
                </div>
                <div class="text-xs text-gray-400 mt-1 truncate">${escapeHtml(j.instruction)}</div>
            </div>
            <div class="flex gap-2 ml-3">
                <button onclick="toggleCron('${j.name}', ${!j.enabled})"
                    class="text-xs px-2 py-1 rounded ${j.enabled ? 'bg-yellow-600/30 text-yellow-400' : 'bg-green-600/30 text-green-400'}">
                    ${j.enabled ? 'Pause' : 'Resume'}
                </button>
                <button onclick="deleteCron('${j.name}')"
                    class="text-xs px-2 py-1 rounded bg-red-600/30 text-red-400">Del</button>
            </div>
        </div>
    `).join('');
}

async function toggleCron(name, enabled) {
    await fetch(`/cron/${name}/toggle`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled }),
    });
    loadCron();
}
async function deleteCron(name) {
    await fetch(`/cron/${name}`, { method: 'DELETE' });
    loadCron();
}

// --- Skills ---
document.getElementById('skill-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('skill-name').value.trim();
    const description = document.getElementById('skill-desc').value.trim();
    const instructions = document.getElementById('skill-instructions').value.trim();
    if (!name || !description || !instructions) return;
    await fetch('/skills', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description, instructions }),
    });
    document.getElementById('skill-name').value = '';
    document.getElementById('skill-desc').value = '';
    document.getElementById('skill-instructions').value = '';
    loadSkills();
});

async function loadSkills() {
    const resp = await fetch('/skills');
    const skills = await resp.json();
    const el = document.getElementById('skills-list');
    if (!skills.length) { el.innerHTML = '<div class="text-gray-500 text-sm">No skills yet. The agent learns as you use it.</div>'; return; }
    el.innerHTML = skills.map(s => `
        <div class="bg-gray-800 rounded-lg p-3">
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                    <span class="font-medium text-sm">${escapeHtml(s.name)}</span>
                    <span class="text-xs text-gray-500">used ${s.use_count}x</span>
                </div>
                <button onclick="deleteSkill('${s.name}')"
                    class="text-xs px-2 py-1 rounded bg-red-600/30 text-red-400">Del</button>
            </div>
            <div class="text-xs text-gray-400 mt-1">${escapeHtml(s.description)}</div>
            <div class="text-xs text-gray-600 mt-1 mono">${escapeHtml(s.instructions).substring(0, 200)}</div>
        </div>
    `).join('');
}
async function deleteSkill(name) {
    await fetch(`/skills/${name}`, { method: 'DELETE' });
    loadSkills();
}

// --- Util ---
function escapeHtml(text) {
    const d = document.createElement('div');
    d.textContent = text;
    return d.innerHTML;
}

// --- Welcome ---
async function loadWelcome() {
    const el = document.getElementById('welcome-msg');
    if (!el) return;
    el.textContent = '...';
    try {
        const resp = await fetch('/welcome');
        const data = await resp.json();
        // Typewriter effect
        const text = data.message || 'Pret.';
        el.textContent = '';
        for (let i = 0; i < text.length; i++) {
            await new Promise(r => setTimeout(r, 18));
            el.textContent = text.slice(0, i + 1);
        }
    } catch(e) {
        el.textContent = 'Pret. Dis-moi ce qu\'on fait.';
    }
}

// --- Init ---
connectWS();
loadWelcome();
