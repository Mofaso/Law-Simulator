
import explainability
import time

print("Testing Explainability Module...")
try:
    explainability.init_recorder(None, "FAKE_KEY")
    print("Recorder initialized.")
    
    @explainability.explainable("test_event")
    def test_func(x):
        return x * 2
        
    print("Calling wrapped function...")
    res = test_func(10)
    print(f"Result: {res}")
    
    time.sleep(1)
    
    with open("explanations.json", "r") as f:
        print("File content:", f.read())
        
except Exception as e:
    print(f"Error: {e}")
