# explainability.py
import threading
import json
import os
import time
import uuid
from datetime import datetime
import functools
import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError

# Configuration
EXPLANATIONS_DB_PATH = "explanations.json"

class ExplainabilityRecorder:
    def __init__(self, model_instance, genai_key=None):
        self.model = model_instance
        self.genai_key = genai_key
        # Ensure file exists
        if not os.path.exists(EXPLANATIONS_DB_PATH):
            with open(EXPLANATIONS_DB_PATH, "w") as f:
                json.dump([], f)

    def _load_records(self):
        try:
            with open(EXPLANATIONS_DB_PATH, "r") as f:
                return json.load(f)
        except:
            return []

    def _save_record(self, record):
        """Thread-safe append to JSON file (naive implementation for MVP)."""
        # In a real DB, this is just an insert.
        # For file-based, we read-lock-write.
        # Using a lock to prevent race conditions in threads
        lock = threading.Lock()
        with lock:
            try:
                records = self._load_records()
                records.append(record)
                with open(EXPLANATIONS_DB_PATH, "w") as f:
                    json.dump(records, f, indent=2)
            except Exception as e:
                print(f"❌ EXPL: Error saving record: {e}")

    def generate_post_hoc_explanation(self, context_id, function_name, input_data, output_data):
        """
        Passive Observer Logic:
        Asks the AI to explain the *already generated* output.
        Does NOT affect the simulation result.
        """
        if not self.model:
            return
        
        print(f"🕵️ EXPL: Generating post-hoc explanation for {context_id}...")
        
        prompt = f"""
        You are an Explainable AI (XAI) Auditor.
        A legal simulation has just been run. Your job is to explain WHY the system produced the following output based on the input.
        
        INPUT CONTEXT:
        Function: {function_name}
        Input Data: {json.dumps(input_data, default=str)}
        
        GENERATED OUTPUT:
        {json.dumps(output_data, default=str)}
        
        TASK:
        1. Identify the key reasoning steps that likely led to this output.
        2. Highlight the specific evidence (words/phrases) in the input that triggered findings.
        3. Explain any trade-offs (e.g., why a positive aspect was weighed against a negative one).
        4. Provide a "Counterfactual Hint": What single change in the input would likely have reversed the outcome?
        
        Return ONLY valid JSON:
        {{
            "reasoning_trace": ["step 1", "step 2"],
            "evidence_links": ["quote from input"],
            "trade_offs": "explanation string",
            "counterfactual_hint": "string"
        }}
        """
        
        try:
            response = self.model.generate_content(prompt)
            explanation_json = response.text
            # Clean logging
            print(f"✅ EXPL: Explanation generated for {context_id}")
            
            # Update the record with this new insight
            self._update_record(context_id, {
                "xai_explanation": explanation_json, 
                "xai_status": "COMPLETED",
                "xai_timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            print(f"⚠️ EXPL: Failed to generate explanation: {e}")
            self._update_record(context_id, {"xai_status": "FAILED", "xai_error": str(e)})

    def _update_record(self, context_id, update_dict):
        lock = threading.Lock()
        with lock:
            try:
                records = self._load_records()
                found = False
                for r in records:
                    if r.get("context_id") == context_id:
                        r.update(update_dict)
                        found = True
                        break
                if found:
                    with open(EXPLANATIONS_DB_PATH, "w") as f:
                        json.dump(records, f, indent=2)
            except Exception as e:
                print(f"❌ EXPL: Error updating record: {e}")

    def record_event(self, function_name, inputs, outputs, user_id=None):
        """
        Main entry point. Records the event and triggers background explanation.
        """
        context_id = str(uuid.uuid4())
        
        record = {
            "context_id": context_id,
            "timestamp": datetime.now().isoformat(),
            "function": function_name,
            "user_id": str(user_id),
            "inputs": inputs, # Sanitize if needed
            "outputs": outputs, # Sanitize if needed
            "xai_status": "PENDING"
        }
        
        self._save_record(record)
        
        # Trigger background explanation
        threading.Thread(
            target=self.generate_post_hoc_explanation,
            args=(context_id, function_name, inputs, outputs),
            daemon=True
        ).start()
        
        return context_id

# Global instance
recorder = None

def init_recorder(model_instance, key):
    global recorder
    recorder = ExplainabilityRecorder(model_instance, key)

def explainable(event_name):
    """Decorator to wrap functions."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # print(f"DEBUG: Decorator invoked for {func.__name__} | Recorder: {recorder}")
            result = func(*args, **kwargs)
            
            # Safe capture - never break app
            try:
                if recorder:
                    # Capture args as dict
                    # Note: We rely on args/kwargs being serializable
                    input_snapshot = {
                        "args": [str(a) for a in args], 
                        "kwargs": {k:str(v) for k,v in kwargs.items()}
                    }
                    
                    # Try to get user_id if valid
                    import flask_login
                    uid = None
                    try:
                        if flask_login.current_user.is_authenticated:
                            uid = flask_login.current_user.id
                    except:
                        pass
                        
                    recorder.record_event(event_name, input_snapshot, result, user_id=uid)
                else:
                    print(f"⚠️ EXPL: Recorder is None during {func.__name__}")
            except Exception as e:
                print(f"⚠️ EXPL: Error in decorator wrapper: {e}")
                
            return result
        return wrapper
    return decorator
