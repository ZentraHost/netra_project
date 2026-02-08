/**
 * NETRA - UI Manager
 * Handles DOM references and updates.
 */

import { STATE } from './config.js';

// DOM Elements
export const UI = {
    cam: document.getElementById('cam'),
    body: document.body,
    
    // Status
    statusPill: document.getElementById('statusPill'),
    statusDot: document.getElementById('statusDot'),
    statusText: document.getElementById('statusText'),
    searchBanner: document.getElementById('searchBanner'),
    mainFeedback: document.getElementById('mainFeedback'),
    gestureHint: document.getElementById('gestureHint'),

    // Task HUD
    taskHud: document.getElementById('task-hud'),
    taskList: document.getElementById('taskList'),
    taskFeedback: document.getElementById('taskFeedback'),

    // Intel Grid
    intelLayer: document.getElementById('intelligence-layer'),
    thinkingBox: document.getElementById('thinkingBox'),
    socialCue: document.getElementById('socialCue'),
    envCue: document.getElementById('envCue'),
    objList: document.getElementById('objList'),
    objCount: document.getElementById('objCount'),
    compassVal: document.getElementById('compassVal'),
    
    // Telemetry
    distVal: document.getElementById('distVal'),
    dirVal: document.getElementById('dirVal'),
    latVal: document.getElementById('latVal')
};

// --- Helpers ---

export function showFeedback(text) {
    UI.mainFeedback.textContent = text;
    UI.mainFeedback.classList.add('visible');
    setTimeout(() => UI.mainFeedback.classList.remove('visible'), 1500);
}

export function updateStatus(text, stateClass) {
    UI.statusText.textContent = text;
    UI.statusDot.className = `status-dot ${stateClass}`;
}

export function toggleIntelLayer() {
    STATE.debug = !STATE.debug;
    if (STATE.debug) {
        UI.intelLayer.classList.add('visible');
        if(window.spatialAudio) window.spatialAudio.playTone(800, 'sine', 0.1);
        showFeedback('INTEL ON');
    } else {
        UI.intelLayer.classList.remove('visible');
        if(window.spatialAudio) window.spatialAudio.playTone(400, 'sine', 0.1);
        showFeedback('INTEL OFF');
    }
}

// --- Mode Specific Updates ---

export function updateNavUI(data) {
    const { thinking, distance, direction, social_cues, environment, objects, ms, current_goal } = data;

    // Search Goal
    if (current_goal) {
        UI.searchBanner.classList.add('visible');
        UI.searchBanner.textContent = `SEARCH: ${current_goal}`;
    } else {
        UI.searchBanner.classList.remove('visible');
    }

    if (thinking) UI.thinkingBox.textContent = thinking;
    
    // Social Cues
    if (social_cues && social_cues.intent && social_cues.intent !== 'none') {
        UI.socialCue.style.display = 'block';
        UI.socialCue.innerHTML = `👥 <b>Social:</b> ${social_cues.details || social_cues.intent}`;
    } else {
        UI.socialCue.style.display = 'none';
    }

    // Env Cues
    if (environment && environment.occupancy === 'occupied') {
        UI.envCue.style.display = 'block';
        UI.envCue.innerHTML = `🚧 <b>Env:</b> ${environment.markers?.[0] || 'Obstruction'}`;
    } else {
        UI.envCue.style.display = 'none';
    }

    // Telemetry
    UI.distVal.innerHTML = distance < 1 ? `${Math.round(distance * 100)}<small>cm</small>` : `${distance.toFixed(1)}<small>m</small>`;
    UI.dirVal.textContent = direction || '--';
    UI.latVal.innerHTML = `${ms}<small>ms</small>`;

    // Objects
    if (!objects || objects.length === 0) {
        UI.objList.innerHTML = '<div style="color:var(--text-mute); font-size:12px; padding:10px; text-align:center;">Scanning...</div>';
    } else {
        UI.objCount.textContent = objects.length;
        UI.objList.innerHTML = objects.map(obj => {
            const isNear = (obj.distance || 99) < 1;
            return `
                <div class="obj-item">
                    <span>${obj.name}</span>
                    <span class="obj-dist ${isNear ? 'near' : ''}">${obj.distance?.toFixed(1)}m</span>
                </div>`;
        }).join('');
    }
}

export function updateMicroUI(data) {
    UI.latVal.innerHTML = `${data.ms}<small>ms</small>`;
}

export function updateTaskUI(data) {
    const { plan, current_step_index, visual_feedback, ms } = data;

    UI.taskHud.classList.add('visible');
    UI.taskFeedback.textContent = visual_feedback || "";
    UI.latVal.innerHTML = `${ms}<small>ms</small>`;

    UI.taskList.innerHTML = plan.map((step, idx) => {
        let cls = '';
        if (idx < current_step_index) cls = 'completed';
        else if (idx === current_step_index) cls = 'active';
        
        return `
            <div class="task-step ${cls}">
                <div class="step-num">${idx + 1}</div>
                <div>${step.instruction}</div>
            </div>`;
    }).join('');

    if (current_step_index >= plan.length) {
        setTimeout(() => UI.taskHud.classList.remove('visible'), 5000);
    }
}

export function updateInquiryUI(data) {
    const { thinking, current_goal, ms } = data;
    if (thinking) UI.thinkingBox.textContent = thinking;
    if (current_goal) {
        UI.searchBanner.classList.add('visible');
        UI.searchBanner.textContent = `SEARCH: ${current_goal}`;
    } else {
        UI.searchBanner.classList.remove('visible');
    }
    UI.latVal.innerHTML = `${ms}<small>ms</small>`;
}
