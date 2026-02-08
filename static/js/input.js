/**
 * NETRA - Input Handlers
 * Gestures, Shake, Compass, Audio Recording.
 */

import { STATE, CONFIG } from './config.js';
import { toggleSystem, checkDebugOverlay } from './main.js'; // Imports form Main
import { toggleIntelLayer, showFeedback, UI } from './ui.js';
import { sendInquiryData } from './network.js';

// --- Gestures ---

let tapTime = 0;
let holdTimer = null;
let isHolding = false;

export function setupInputs() {
    document.body.addEventListener('touchstart', handleTouchStart, { passive: false });
    document.body.addEventListener('touchend', handleTouchEnd);
    
    window.addEventListener('devicemotion', handleMotion);
    
    if (window.DeviceOrientationEvent) {
        window.addEventListener('deviceorientation', handleOrientation);
    }
}

function handleTouchStart(e) {
    // 1. Debug Toggle (Three fingers)
    if (e.touches.length === 3) {
        checkDebugOverlay();
        return;
    }

    // Ignore if touching debug grid
    if (e.target.closest('#intelligence-layer') && STATE.debug) return;

    const now = Date.now();
    
    // 2. Double Tap (Toggle System)
    if (now - tapTime < 300) {
        toggleSystem();
        tapTime = 0;
        return;
    }
    tapTime = now;
    
    // 3. Hold (Record)
    isHolding = false;
    holdTimer = setTimeout(() => {
        isHolding = true;
        startRecording();
    }, 600);
}

function handleTouchEnd() {
    if (holdTimer) clearTimeout(holdTimer);
    if (isHolding) stopRecording();
}

// --- Sensors ---

function handleMotion(e) {
    const { x, y, z } = e.accelerationIncludingGravity || {};
    if (!x) return;
    
    const mag = Math.abs(Math.sqrt(x*x + y*y + z*z) - 9.8);
    if (mag > 20 && (Date.now() - STATE.lastShake > 1000)) {
        STATE.lastShake = Date.now();
        toggleIntelLayer();
    }
}

function handleOrientation(e) {
    if (e.webkitCompassHeading) {
        STATE.heading = Math.round(e.webkitCompassHeading);
    } else if (e.alpha) {
        STATE.heading = Math.round(360 - e.alpha);
    }
    UI.compassVal.textContent = `${STATE.heading}°`;
}

// --- Audio Recording ---

let mediaRecorder = null;
let audioChunks = [];

async function startRecording() {
    if (!STATE.active) {
        showFeedback('START FIRST');
        return;
    }

    showFeedback('LISTENING...');
    window.speechSynthesis.cancel();
    if(window.spatialAudio) window.spatialAudio.playTone(880, 'sine', 0.1);

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];
        
        mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
        mediaRecorder.start();
        
    } catch (e) {
        console.error("Microphone Error:", e);
        showFeedback('MIC BLOCKED');
    }
}

function stopRecording() {
    if (!mediaRecorder || mediaRecorder.state !== 'recording') return;
    
    mediaRecorder.stop();
    showFeedback('THINKING...');
    if(window.spatialAudio) window.spatialAudio.playTone(440, 'sine', 0.1);

    mediaRecorder.onstop = () => {
        const blob = new Blob(audioChunks, { type: 'audio/webm' });
        const reader = new FileReader();
        reader.readAsDataURL(blob);
        reader.onloadend = () => {
            // Context capture
            const cvs = document.createElement('canvas');
            cvs.width = CONFIG.imgWidth;
            cvs.height = Math.round(CONFIG.imgWidth * 0.75); // 4:3
            const ctx = cvs.getContext('2d');
            ctx.drawImage(UI.cam, 0, 0, cvs.width, cvs.height);
            
            sendInquiryData(cvs.toDataURL('image/jpeg', 0.6), reader.result);
        };
        
        // Cleanup
        mediaRecorder.stream.getTracks().forEach(t => t.stop());
    };
}
