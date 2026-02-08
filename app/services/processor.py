"""
NETRA AI Processor Service
==========================
Core service for processing video frames and audio inputs using Google's Gemini AI.
Handles asynchronous API calls, image optimization, and task state management.
"""

import os
import io
import json
import time
import asyncio
import base64
import logging
import traceback
from typing import Dict, Any, Optional, List, Union

from fastapi import WebSocket
from PIL import Image
from google import genai
from google.genai import types

from ..config import IMAGE_SIZE, MODEL_NAME, MODEL_TIMEOUT, GEMINI_KEY
from ..prompts import (
    AI_PROMPT,
    MICRO_NAV_PROMPT,
    INQUIRY_PROMPT,
    TASK_PLANNER_PROMPT,
    TASK_GUIDANCE_PROMPT
)
from ..models import SessionState, TaskState, GlobalTaskState
from ..utils import Console, format_distance_speech
from .memory import memory_store

# Initialize Gemini Client
if not GEMINI_KEY:
    logging.critical("GEMINI_KEY is missing. Processor will fail.")
client = genai.Client(api_key=GEMINI_KEY)

# Global task state instance (persists across connection drops)
global_task_state = GlobalTaskState()


# =============================================================================
# CPU-BOUND HELPER FUNCTIONS (Run in ThreadPool)
# =============================================================================

def _process_image_sync(image_bytes: bytes, size: tuple) -> Image.Image:
    """Decode and resize image bytes."""
    with io.BytesIO(image_bytes) as bio:
        img = Image.open(bio)
        img.load()  # Force load
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail(size, Image.Resampling.LANCZOS)
    return img


def _process_base64_image_sync(b64_str: str, size: tuple) -> Image.Image:
    """Decode base64 string and resize image."""
    try:
        header, encoded = b64_str.split(",", 1)
        data = base64.b64decode(encoded)
        return _process_image_sync(data, size)
    except Exception as e:
        logging.error(f"Base64 image decode error: {e}")
        # Return a blank black image to prevent crash
        return Image.new("RGB", size, (0, 0, 0))


def _decode_base64_audio_sync(b64_str: str) -> bytes:
    """Decode base64 audio string."""
    try:
        _, encoded = b64_str.split(",", 1)
        return base64.b64decode(encoded)
    except Exception as e:
        logging.error(f"Base64 audio decode error: {e}")
        return b""


def _parse_json_sync(text: str) -> Any:
    """Safely parse JSON string, cleaning markdown code blocks if present."""
    clean_text = text.strip()
    if clean_text.startswith("```json"):
        clean_text = clean_text[7:]
    if clean_text.startswith("```"):
        clean_text = clean_text[3:]
    if clean_text.endswith("```"):
        clean_text = clean_text[:-3]
    return json.loads(clean_text)


# =============================================================================
# ASYNC UTILITIES
# =============================================================================

async def safe_send_json(websocket: WebSocket, data: Dict[str, Any]) -> bool:
    """
    Safely send JSON data to a websocket, handling disconnects.
    Returns True if sent, False if failed/closed.
    """
    try:
        await websocket.send_json(data)
        return True
    except RuntimeError as e:
        # "Cannot call 'send' once a close message has been sent"
        if "close" in str(e).lower():
            return False
        logging.warning(f"WebSocket Runtime Error: {e}")
        return False
    except Exception as e:
        logging.warning(f"WebSocket Send Error: {e}")
        return False


# =============================================================================
# CORE PROCESSING FUNCTIONS
# =============================================================================

async def process_micro_frame(frame_data: Dict[str, Any], state: SessionState, websocket: WebSocket) -> None:
    """
    Process a frame for Micro-Navigation (High speed, low latency).
    Target: Hand guidance to specific small objects.
    """
    image_bytes = frame_data.get("image")
    target = state.micro_target
    start_proc = time.perf_counter()
    
    if not image_bytes or not target:
        return

    try:
        # 1. Optimize Image
        img = await asyncio.to_thread(_process_image_sync, image_bytes, (224, 224))

        # 2. Call Gemini
        # Using Flash 2.0 for speed
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.0-flash",
            contents=[MICRO_NAV_PROMPT.format(target=target), img],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
        )

        # 3. Parse Result
        if not response.text:
            return

        result = await asyncio.to_thread(_parse_json_sync, response.text)
        
        proc_time = int((time.perf_counter() - start_proc) * 1000)
        state.frames_processed += 1
        
        # 4. Send Response
        await safe_send_json(websocket, {
            "type": "micro_result",
            "x": result.get("x", 0),
            "y": result.get("y", 0),
            "action": result.get("action", "move"),
            "guidance_speech": result.get("guidance_speech"),
            "ms": proc_time
        })

    except Exception as e:
        logging.error(f"Micro-Nav Error: {e}")
        state.frames_skipped += 1


async def process_task_frame(frame_data: Dict[str, Any], state: SessionState, websocket: WebSocket) -> None:
    """
    Process a frame for Interactive Task Guidance.
    Verifies if a step is complete and provides feedback.
    """
    # Quick state check
    if not state.task_state.is_active or not state.task_state.plan:
        state.mode = "nav"
        return

    idx = state.task_state.current_step_index
    # Check if task is already done
    if idx >= len(state.task_state.plan):
        await safe_send_json(websocket, {"type": "speak", "text": "Task already completed."})
        state.task_state = TaskState() # Reset
        state.mode = "nav"
        return

    image_bytes = frame_data.get("image")
    current_step = state.task_state.plan[idx]
    start_proc = time.perf_counter()

    try:
        # 1. Optimize Image
        img = await asyncio.to_thread(_process_image_sync, image_bytes, IMAGE_SIZE)

        # 2. Call Gemini
        prompt = TASK_GUIDANCE_PROMPT.format(current_step=current_step['instruction'])
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.0-flash",
            contents=[prompt, img],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
        )

        # 3. Parse & Logic
        if not response.text:
            return
            
        result = await asyncio.to_thread(_parse_json_sync, response.text)
        
        step_completed = result.get("step_completed", False)
        speech = result.get("speech", "")
        visual_feedback = result.get("visual_feedback", "")
        
        if step_completed:
            state.task_state.plan[idx]['completed'] = True
            state.task_state.current_step_index += 1
            
            # Check if that was the last step
            if state.task_state.current_step_index >= len(state.task_state.plan):
                await safe_send_json(websocket, {"type": "speak", "text": "Task completed! Great job."})
                state.task_state.is_active = False
                state.mode = "nav"
            else:
                next_step = state.task_state.plan[state.task_state.current_step_index]
                next_speech = f"Step done. Next: {next_step['instruction']}"
                await safe_send_json(websocket, {"type": "speak", "text": next_speech})
        
        elif speech:
            # Use speech manager to prevent spamming the same guidance
            speak, _ = state.speech_manager.should_speak("medium", "task", "guidance", "task", 1.0, speech)
            if speak:
                state.speech_manager.record_speech(speech, "medium", "task", "guidance", "task", 1.0)
                await safe_send_json(websocket, {"type": "speak", "text": speech})

        # 4. Sync Global State
        global_task_state.update_from(state.task_state)

        # 5. UI Update
        proc_time = int((time.perf_counter() - start_proc) * 1000)
        state.frames_processed += 1
        
        await safe_send_json(websocket, {
            "type": "task_update",
            "plan": state.task_state.plan,
            "current_step_index": state.task_state.current_step_index,
            "visual_feedback": visual_feedback,
            "ms": proc_time
        })

    except Exception as e:
        logging.error(f"Task Guidance Error: {e}")
        state.frames_skipped += 1


async def process_frame(frame_data: Dict[str, Any], state: SessionState, websocket: WebSocket) -> None:
    """
    Standard Navigation Mode Processing.
    Detects objects, social cues, safety hazards, and updates memory.
    """
    image_bytes = frame_data.get("image")
    heading = frame_data.get("heading", 0)
    task_desc = f"SEARCHING FOR: {state.current_goal}" if state.current_goal else "General Guidance"
    
    start_proc = time.perf_counter()

    try:
        # 1. Optimize Image
        img = await asyncio.to_thread(_process_image_sync, image_bytes, IMAGE_SIZE)

        # 2. Build Context
        memory_context = state.get_memory_context()
        known_locs = memory_store.get_location_summary()
        # Get last 3 social context items
        temporal_context = " | ".join(list(state.social_context)[-3:]) if state.social_context else "None"

        # 3. Call Gemini
        formatted_prompt = AI_PROMPT.format(
            heading=heading,
            task=task_desc,
            memory=memory_context,
            known_locations=known_locs,
            temporal_context=temporal_context
        )

        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.models.generate_content,
                model=MODEL_NAME,
                contents=[formatted_prompt, img],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                    # thinking_config removed as it's model-specific and sometimes causes errors in standard Flash
                )
            ),
            timeout=MODEL_TIMEOUT
        )

        # 4. Parse JSON
        if not response.text:
            logging.warning("Model returned empty response.")
            return

        result = await asyncio.to_thread(_parse_json_sync, response.text)
        
        # Extract fields with safe defaults
        prio = result.get("priority", "low").lower()
        category = result.get("category", "navigation")
        subject = result.get("subject", "")
        dist = float(result.get("distance", 2.0))
        direction = result.get("direction", "ahead")
        speech_text = result.get("speech", "")
        scene_desc = result.get("scene_description", "")
        target_detected = result.get("target_detected", False)
        
        # 5. Pipeline Logic
        
        # Social Buffer Update
        if scene_desc:
            state.social_context.append(scene_desc)

        # Persistent Memory Logging
        if subject and category in ["target", "social", "text", "furniture"]:
            loc_tag = result.get("current_location_tag")
            memory_store.log_object(subject, loc_tag, scene_desc)

        # Short-term Memory Update
        if subject:
            state.update_memory(subject, direction, dist, category)

        # Target Found Alert
        if target_detected and state.current_goal:
             # Basic string matching; could be fuzzy
            if state.current_goal.lower() in subject.lower():
                Console.log('human', f"Target Found: {state.current_goal}", 'green')

        # Distance Speech formatting (append "2 meters" if not in text)
        if speech_text and dist > 0:
            dist_str = format_distance_speech(dist)
            # Simple check to see if distance is already mentioned
            if str(int(dist)) not in speech_text:
                speech_text = f"{speech_text} {dist_str} away."

        # Speech Decision
        speak, reason = state.speech_manager.should_speak(
            prio, subject, direction, category, dist, speech_text
        )
        
        if speak and speech_text:
            state.speech_manager.record_speech(speech_text, prio, subject, direction, category, dist)
            await safe_send_json(websocket, {"type": "speak", "text": speech_text})

        # Tracker Processing
        raw_objects = result.get("objects", [])
        stable_objects = state.tracker.process_detections(raw_objects)
        
        # Prepare UI Payload
        ui_objects = [
            {"name": o.name, "distance": o.distance, "category": o.category} 
            for o in stable_objects
        ] if stable_objects else raw_objects[:5]

        proc_time = int((time.perf_counter() - start_proc) * 1000)
        state.frames_processed += 1

        await safe_send_json(websocket, {
            "type": "result",
            "priority": prio,
            "distance": dist,
            "direction": direction,
            "target_detected": target_detected,
            "current_goal": state.current_goal,
            "social_cues": result.get("social_cues", {}),
            "environment": result.get("environment", {}),
            "objects": ui_objects,
            "scene": scene_desc,
            "ms": proc_time,
            "stats": {
                "received": state.frames_received,
                "processed": state.frames_processed
            }
        })

        Console.detection(prio, scene_desc or subject, dist, speech_text, speak, proc_time, reason)

    except asyncio.TimeoutError:
        logging.warning("AI Model Timed Out")
        state.frames_skipped += 1
    except Exception as e:
        logging.error(f"Nav Process Error: {e}")
        traceback.print_exc()
        state.frames_skipped += 1


async def process_inquiry(data: Dict[str, Any], state: SessionState, websocket: WebSocket) -> None:
    """
    Handle User Voice Inquiries (Multimodal Audio + Video).
    Determines intent (Nav, Search, Task, etc.) and acts on it.
    """
    image_b64 = data.get("image")
    audio_b64 = data.get("audio")
    
    if not image_b64 or not audio_b64:
        return

    start_proc = time.perf_counter()
    Console.log('human', 'Processing user inquiry...', 'magenta')

    try:
        # 1. Decode inputs
        img = await asyncio.to_thread(_process_base64_image_sync, image_b64, IMAGE_SIZE)
        audio_bytes = await asyncio.to_thread(_decode_base64_audio_sync, audio_b64)

        # 2. Build Prompt Context
        if state.task_state.is_active:
            idx = state.task_state.current_step_index
            total = len(state.task_state.plan)
            instr = state.task_state.plan[idx]['instruction'] if idx < total else "Complete"
            task_str = f"ACTIVE TASK: Step {idx + 1}/{total} - '{instr}'"
        else:
            task_str = "No active task"

        prompt = INQUIRY_PROMPT.format(
            history_context=memory_store.get_history_context(),
            task_state=task_str
        )

        # 3. Call Gemini (Audio + Video + Text)
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=MODEL_NAME,
            contents=[
                prompt,
                img,
                types.Part.from_bytes(data=audio_bytes, mime_type="audio/webm")
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )

        # 4. Parse Intent
        if not response.text:
            return

        result = await asyncio.to_thread(_parse_json_sync, response.text)
        
        intent = result.get("intent", "info")
        speech_text = result.get("speech", "I didn't catch that.")
        thinking = result.get("thinking", "")
        
        # 5. Handle Intents
        await _handle_intent(intent, result, state, websocket)
        
        # 6. Final UI/Audio Response
        # Update speech text if handler modified it? 
        # For now, we trust the handler or the AI's generation.
        # But some handlers (like task planner) might want to OVERRIDE the speech.
        
        # Let's rely on the AI's speech unless we specifically want to override it in _handle_intent.
        # Ideally _handle_intent should return the speech to say.
        
        # For simplicity, if _handle_intent returns a string, use it.
        handler_speech = await _handle_intent(intent, result, state, websocket)
        if handler_speech:
            speech_text = handler_speech

        proc_time = int((time.perf_counter() - start_proc) * 1000)
        
        await safe_send_json(websocket, {
            "type": "inquiry_result",
            "thinking": thinking,
            "current_goal": state.current_goal,
            "mode": state.mode,
            "task_active": state.task_state.is_active,
            "ms": proc_time
        })
        
        await safe_send_json(websocket, {
            "type": "speak",
            "text": speech_text
        })
        
        Console.log('info', f"Inquiry: {intent}", 'magenta', f"{proc_time}ms")

    except Exception as e:
        logging.error(f"Inquiry Error: {e}")
        traceback.print_exc()
        await safe_send_json(websocket, {"type": "speak", "text": "Sorry, I had an error processing that."})


async def _handle_intent(intent: str, result: Dict, state: SessionState, websocket: WebSocket) -> Optional[str]:
    """
    Execute side-effects based on the determined intent.
    Returns an optional string to override the spoken response.
    """
    if intent == "micro_nav":
        target = result.get("target")
        if target:
            state.mode = "micro"
            state.micro_target = target
            return f"Guiding you to the {target}. Hold steady."

    elif intent == "search":
        state.mode = "nav"
        goal = result.get("search_target") or result.get("goal")
        if goal:
            state.current_goal = goal
            Console.log('human', f"Goal: {goal}", 'magenta')
            return f"Okay, searching for {goal}."

    elif intent == "stop":
        state.mode = "nav"
        state.current_goal = None
        state.micro_target = None
        state.task_state = TaskState() # Clear active task
        global_task_state.is_active = False
        return "Stopping all tasks and searches."

    elif intent == "tag":
        name = result.get("tag_name")
        desc = result.get("scene_description")
        if name and desc:
            memory_store.add_location(name, desc)
            return f"Tagged location as {name}."

    elif intent == "task":
        task_name = result.get("task_name")
        return await _generate_task_plan(task_name, state, websocket)

    elif intent.startswith("task_"):
        return await _handle_task_control(intent, state, websocket)

    return None # Default to using the AI's generated speech


async def _generate_task_plan(task_name: str, state: SessionState, websocket: WebSocket) -> str:
    """Generate a step-by-step plan for a physical task."""
    if not task_name:
        return "I didn't hear a task name."

    Console.log('process', f"Planning task: {task_name}", 'cyan')
    
    try:
        mem_ctx = memory_store.get_history_context()
        loc_ctx = memory_store.get_location_summary()
        full_context = f"{mem_ctx}\nLocations: {loc_ctx}"
        
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=MODEL_NAME,
            contents=[TASK_PLANNER_PROMPT.format(user_query=task_name, memory_context=full_context)],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )

        plan_data = await asyncio.to_thread(_parse_json_sync, response.text)
        
        if isinstance(plan_data, list) and plan_data:
            state.task_state = TaskState(
                is_active=True,
                plan=plan_data,
                current_step_index=0
            )
            state.mode = "task"
            global_task_state.update_from(state.task_state, task_name)
            
            # Send plan to UI
            await safe_send_json(websocket, {
                "type": "task_update",
                "plan": plan_data,
                "current_step_index": 0
            })
            
            first_step = plan_data[0]['instruction']
            return f"Plan generated for {task_name}. First step: {first_step}"
        else:
            return "I couldn't generate a valid plan."
            
    except Exception as e:
        logging.error(f"Task Planning Failed: {e}")
        return "Sorry, I failed to create a plan."


async def _handle_task_control(intent: str, state: SessionState, websocket: WebSocket) -> str:
    """Handle navigation within a task (skip, back, repeat)."""
    if not state.task_state.is_active or not state.task_state.plan:
        return "No active task to control."
        
    ts = state.task_state
    
    if intent == "task_skip" or intent == "task_done":
        ts.plan[ts.current_step_index]['completed'] = True
        ts.current_step_index += 1
        
        if ts.current_step_index >= len(ts.plan):
            ts.is_active = False
            state.mode = "nav"
            global_task_state.is_active = False
            resp_text = "Task completed."
        else:
            next_step = ts.plan[ts.current_step_index]['instruction']
            resp_text = f"Done. Next: {next_step}"

    elif intent == "task_previous":
        if ts.current_step_index > 0:
            ts.current_step_index -= 1
            ts.plan[ts.current_step_index]['completed'] = False
            prev_step = ts.plan[ts.current_step_index]['instruction']
            resp_text = f"Back to: {prev_step}"
        else:
            resp_text = "Already at start."
            
    elif intent == "task_repeat":
        curr = ts.plan[ts.current_step_index]['instruction']
        resp_text = f"Current step: {curr}"
        
    elif intent == "task_status":
        total = len(ts.plan)
        current = ts.current_step_index + 1
        resp_text = f"Step {current} of {total}."
    else:
        resp_text = "Unknown task command."
        
    global_task_state.update_from(ts)
    await safe_send_json(websocket, {
        "type": "task_update",
        "plan": ts.plan,
        "current_step_index": ts.current_step_index
    })
    
    return resp_text
