/**
 * Drone Security Analyst — Frontend Application Logic
 * 
 * Handles video processing via WebSocket, REST API calls, 
 * UI updates, and user interactions for the surveillance dashboard.
 * Supports both real video analysis (VLM) and demo simulation modes.
 */

// ══════════════════════════════════════════════════════════
// CONFIGURATION
// ══════════════════════════════════════════════════════════

const API_BASE = window.location.origin;
const WS_BASE = `ws://${window.location.host}`;

let ws = null;
let isProcessing = false;
let eventLog = [];
let availableVideos = [];

// ══════════════════════════════════════════════════════════
// VIDEO PROCESSING — WebSocket Streaming
// ══════════════════════════════════════════════════════════

function processVideo() {
    if (isProcessing) return;

    const select = document.getElementById('video-select');
    const filename = select.value;

    if (!filename) {
        alert('Please select a drone video first');
        return;
    }

    isProcessing = true;
    updateProcessingUI(true, 'Analyzing Video...');
    clearLog();

    // Open WebSocket for video processing
    ws = new WebSocket(`${WS_BASE}/ws/process-video`);

    ws.onopen = () => {
        console.log('✅ WebSocket connected — sending video selection');
        setStatus('CONNECTING', '#00ff88');

        // Send video selection to server
        ws.send(JSON.stringify({
            filename: filename,
            interval_seconds: 2.0,
            max_frames: 15,
        }));
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setStatus('ERROR', '#ff4444');
        isProcessing = false;
        updateProcessingUI(false);
    };

    ws.onclose = () => {
        console.log('WebSocket closed');
        if (isProcessing) {
            isProcessing = false;
            updateProcessingUI(false);
        }
    };
}

function startDemoSimulation() {
    if (isProcessing) return;

    isProcessing = true;
    updateProcessingUI(true, 'Demo Mode...');
    clearLog();

    ws = new WebSocket(`${WS_BASE}/ws/simulation`);

    ws.onopen = () => {
        console.log('✅ Demo simulation connected');
        setStatus('DEMO MODE', '#f59e0b');
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setStatus('ERROR', '#ff4444');
        isProcessing = false;
        updateProcessingUI(false);
    };

    ws.onclose = () => {
        if (isProcessing) {
            isProcessing = false;
            updateProcessingUI(false);
        }
    };
}

function handleWebSocketMessage(data) {
    switch (data.type) {
        case 'simulation_start':
            showProgress(0, data.total_frames);
            addSystemChatMessage(data.message);
            break;

        case 'frame_processing':
            setStatus(`FRAME ${data.frame_id}`, '#00ff88');
            break;

        case 'vlm_result':
            // VLM has described the image — show interim result
            setStatus(`AI ANALYZING ${data.frame_id}`, '#a78bfa');
            break;

        case 'frame_result':
            renderFrame(data);
            renderEventRow(data);
            renderAlert(data);
            updateProgress(data.progress);
            break;

        case 'simulation_complete':
            setStatus('COMPLETE', '#00ff88');
            isProcessing = false;
            updateProcessingUI(false);
            addSystemChatMessage(data.message);
            hideProgress();
            break;

        case 'error':
            setStatus('ERROR', '#ff4444');
            addSystemChatMessage(`❌ ${data.message}`);
            isProcessing = false;
            updateProcessingUI(false);
            break;
    }
}

// ══════════════════════════════════════════════════════════
// FRAME RENDERING (with image + VLM support)
// ══════════════════════════════════════════════════════════

function renderFrame(data) {
    const frameEmpty = document.getElementById('frame-empty');
    const currentFrame = document.getElementById('current-frame');
    const frameCounter = document.getElementById('frame-counter');

    frameEmpty.classList.add('hidden');
    currentFrame.classList.remove('hidden');

    // Trigger re-animation
    currentFrame.style.animation = 'none';
    currentFrame.offsetHeight;
    currentFrame.style.animation = '';

    frameCounter.textContent = `FRAME ${data.frame_id}`;

    // Update drone camera image
    const droneImage = document.getElementById('drone-image');
    const placeholder = document.getElementById('drone-image-placeholder');

    if (data.image_url) {
        droneImage.src = data.image_url;
        droneImage.style.display = 'block';
        placeholder.classList.add('hidden');
    } else {
        droneImage.style.display = 'none';
        placeholder.classList.remove('hidden');
    }

    // Update VLM description
    const vlmText = document.getElementById('vlm-description-text');
    const vlmDesc = data.vlm_description || data.description || '—';
    vlmText.textContent = vlmDesc;

    // Update telemetry
    document.getElementById('telem-location').textContent = data.location || '—';
    document.getElementById('telem-altitude').textContent = `${data.altitude || '—'}m`;
    document.getElementById('telem-timestamp').textContent = data.timestamp || '—';
    document.getElementById('telem-gps').textContent =
        data.drone_lat ? `${data.drone_lat?.toFixed(4)}, ${data.drone_lon?.toFixed(4)}` : '—';

    // Update analysis
    const analysis = data.analysis || {};
    const riskLevel = (analysis.risk_level || 'Low').toLowerCase();

    const riskBadge = document.getElementById('risk-badge');
    riskBadge.textContent = analysis.risk_level || 'Low';
    riskBadge.className = `risk-badge ${riskLevel}`;

    document.getElementById('analysis-summary').textContent =
        analysis.event_summary || '—';
    document.getElementById('analysis-alert').textContent =
        analysis.alert_message || 'No alert';
    document.getElementById('analysis-reasoning').textContent =
        analysis.reasoning || '—';

    const objectsContainer = document.getElementById('analysis-objects');
    objectsContainer.innerHTML = '';
    const objects = analysis.detected_objects || [];
    objects.forEach(obj => {
        const tag = document.createElement('span');
        tag.className = 'object-tag';
        tag.textContent = obj;
        objectsContainer.appendChild(tag);
    });
}

// ══════════════════════════════════════════════════════════
// EVENT LOG TABLE
// ══════════════════════════════════════════════════════════

function renderEventRow(data) {
    const analysis = data.analysis || {};
    const riskLevel = (analysis.risk_level || 'Low').toLowerCase();
    const vlmDesc = data.vlm_description || data.description || analysis.event_summary || '—';

    eventLog.push(data);

    const tbody = document.getElementById('event-table-body');
    const row = document.createElement('tr');
    row.style.animation = 'fadeIn 0.3s ease';
    row.dataset.searchText = [
        data.frame_id,
        data.timestamp,
        data.location,
        analysis.risk_level,
        vlmDesc,
        (analysis.detected_objects || []).join(' ')
    ].join(' ').toLowerCase();

    row.innerHTML = `
        <td class="td-id">#${data.frame_id}</td>
        <td class="td-time">${data.timestamp || '—'}</td>
        <td class="td-location">${data.location || '—'}</td>
        <td class="td-risk ${riskLevel}">${analysis.risk_level || 'Low'}</td>
        <td title="${vlmDesc}">${vlmDesc.substring(0, 80)}${vlmDesc.length > 80 ? '...' : ''}</td>
        <td>${(analysis.detected_objects || []).join(', ') || '—'}</td>
    `;

    tbody.appendChild(row);
    document.getElementById('event-count').textContent = `${eventLog.length} events`;
}

function filterTable() {
    const query = document.getElementById('filter-input').value.toLowerCase();
    const rows = document.querySelectorAll('#event-table-body tr');

    rows.forEach(row => {
        const text = row.dataset.searchText || '';
        row.style.display = text.includes(query) ? '' : 'none';
    });
}

// ══════════════════════════════════════════════════════════
// ALERTS PANEL
// ══════════════════════════════════════════════════════════

function renderAlert(data) {
    const analysis = data.analysis || {};
    const riskLevel = (analysis.risk_level || 'Low').toLowerCase();

    if (riskLevel !== 'high' && riskLevel !== 'critical' && riskLevel !== 'medium') return;

    const container = document.getElementById('alerts-container');
    const card = document.createElement('div');
    card.className = `alert-card ${riskLevel}`;
    card.innerHTML = `
        <div><strong>${analysis.risk_level}:</strong> ${analysis.alert_message || analysis.event_summary || 'Alert triggered'}</div>
        <div class="alert-time">Frame #${data.frame_id} — ${data.timestamp} — ${data.location}</div>
    `;
    container.prepend(card);
}

// ══════════════════════════════════════════════════════════
// CHAT
// ══════════════════════════════════════════════════════════

async function sendChat() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    if (!message) return;

    addChatMessage(message, 'user');
    input.value = '';

    const sendBtn = document.getElementById('chat-send-btn');
    sendBtn.disabled = true;

    try {
        const response = await fetch(`${API_BASE}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message }),
        });

        const data = await response.json();
        addChatMessage(data.response, 'agent');
    } catch (error) {
        addChatMessage(`Error: ${error.message}`, 'system');
    } finally {
        sendBtn.disabled = false;
    }
}

function addChatMessage(text, type) {
    const container = document.getElementById('chat-messages');
    const div = document.createElement('div');
    div.className = `chat-message ${type}`;
    div.textContent = text;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function addSystemChatMessage(text) {
    addChatMessage(text, 'system');
}

// ══════════════════════════════════════════════════════════
// SUMMARY
// ══════════════════════════════════════════════════════════

async function generateSummary() {
    const overlay = document.getElementById('summary-overlay');
    const content = document.getElementById('summary-content');

    overlay.classList.remove('hidden');
    content.textContent = 'Generating AI video summary...';

    try {
        const response = await fetch(`${API_BASE}/api/summary`);
        const data = await response.json();
        content.textContent = data.summary;
    } catch (error) {
        content.textContent = `Error generating summary: ${error.message}`;
    }
}

function closeSummary(event) {
    if (event && event.target !== event.currentTarget) return;
    document.getElementById('summary-overlay').classList.add('hidden');
}

// ══════════════════════════════════════════════════════════
// VIDEO SELECTOR
// ══════════════════════════════════════════════════════════

async function loadVideos() {
    try {
        const response = await fetch(`${API_BASE}/api/videos`);
        const data = await response.json();
        availableVideos = data.videos || [];

        const select = document.getElementById('video-select');
        select.innerHTML = '';

        if (availableVideos.length === 0) {
            select.innerHTML = '<option value="">No videos found — place .mp4 files in /videos/</option>';
            return;
        }

        select.innerHTML = '<option value="">Choose a drone video...</option>';
        availableVideos.forEach(video => {
            const option = document.createElement('option');
            option.value = video.filename;
            option.textContent = `📹 ${video.filename}`;
            select.appendChild(option);
        });

        select.addEventListener('change', () => {
            const selected = availableVideos.find(v => v.filename === select.value);
            const infoEl = document.getElementById('video-info');
            if (selected) {
                infoEl.textContent = `${selected.duration_seconds?.toFixed(1)}s · ${selected.width}×${selected.height} · ${selected.fps?.toFixed(0)}fps`;
            } else {
                infoEl.textContent = '';
            }
        });

    } catch (error) {
        console.error('Failed to load videos:', error);
        document.getElementById('video-select').innerHTML =
            '<option value="">Error loading videos</option>';
    }
}

// ══════════════════════════════════════════════════════════
// CONTROLS & UI HELPERS
// ══════════════════════════════════════════════════════════

function clearLog() {
    eventLog = [];
    document.getElementById('event-table-body').innerHTML = '';
    document.getElementById('event-count').textContent = '0 events';
    document.getElementById('alerts-container').innerHTML = '';
    document.getElementById('frame-empty').classList.remove('hidden');
    document.getElementById('current-frame').classList.add('hidden');
    document.getElementById('frame-counter').textContent = 'NO FRAME';
    document.getElementById('filter-input').value = '';
}

function updateProcessingUI(running, label = 'Analyzing...') {
    const btn = document.getElementById('btn-process-video');
    const demoBtn = document.getElementById('btn-demo');

    if (running) {
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner"></span> ${label}`;
        demoBtn.disabled = true;
    } else {
        btn.disabled = false;
        btn.innerHTML = '▶ Analyze Video';
        demoBtn.disabled = false;
    }
}

function setStatus(text, color) {
    const indicator = document.getElementById('status-indicator');
    indicator.innerHTML = `<span style="color: ${color}">● ${text}</span>`;
}

function showProgress(current, total) {
    const container = document.getElementById('progress-container');
    container.classList.remove('hidden');
    updateProgressValues(current, total);
}

function updateProgress(progressStr) {
    const parts = progressStr.split('/');
    if (parts.length === 2) {
        const current = parseInt(parts[0]);
        const total = parseInt(parts[1]);
        updateProgressValues(current, total);
    }
}

function updateProgressValues(current, total) {
    const pct = total > 0 ? (current / total) * 100 : 0;
    document.getElementById('progress-bar').style.width = `${pct}%`;
    document.getElementById('progress-count').textContent = `${current}/${total}`;
    document.getElementById('progress-label').textContent =
        current >= total ? 'Complete!' : 'Processing frames...';
}

function hideProgress() {
    setTimeout(() => {
        document.getElementById('progress-container').classList.add('hidden');
    }, 3000);
}

// ══════════════════════════════════════════════════════════
// INITIALIZATION
// ══════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', async () => {
    console.log('🛸 Drone Security Analyst Dashboard v2.0 initialized');

    // Load available videos
    await loadVideos();

    // Check API status
    try {
        const response = await fetch(`${API_BASE}/api/status`);
        const status = await response.json();
        console.log('API Status:', status);

        // Load existing frames if any
        if (status.indexed_frames > 0) {
            const framesResponse = await fetch(`${API_BASE}/api/frames`);
            const framesData = await framesResponse.json();

            if (framesData.frames && framesData.frames.length > 0) {
                framesData.frames.forEach(frame => {
                    const frameData = {
                        frame_id: frame.frame_id,
                        timestamp: frame.timestamp,
                        location: frame.location,
                        description: frame.description,
                        vlm_description: frame.vlm_description || frame.description,
                        image_url: frame.image_path ? `/extracted_frames/${frame.image_path}` : null,
                        analysis: {
                            detected_objects: frame.detected_objects,
                            risk_level: frame.risk_level,
                            alert_message: frame.alert_message,
                            event_summary: frame.event_summary,
                        }
                    };
                    renderEventRow(frameData);
                    renderAlert(frameData);
                });

                const lastFrame = framesData.frames[framesData.frames.length - 1];
                renderFrame({
                    ...lastFrame,
                    vlm_description: lastFrame.vlm_description || lastFrame.description,
                    image_url: lastFrame.image_path ? `/extracted_frames/${lastFrame.image_path}` : null,
                    analysis: {
                        detected_objects: lastFrame.detected_objects,
                        risk_level: lastFrame.risk_level,
                        alert_message: lastFrame.alert_message,
                        event_summary: lastFrame.event_summary,
                    }
                });

                addSystemChatMessage(`Loaded ${framesData.frames.length} previously analyzed frames.`);
            }
        }

        setStatus('ONLINE', '#00ff88');
    } catch (error) {
        console.error('API not available:', error);
        setStatus('OFFLINE', '#ff4444');
    }
});
