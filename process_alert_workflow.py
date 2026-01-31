import os
import json
import logging
import urllib.request
import urllib.error
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def load_json_file(filepath: str) -> Any:
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"File not found: {filepath}")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON {filepath}: {e}")
        return None

def retrieve_knowledge_from_api(decision: str) -> List[Dict]:
    """
    Retrieve knowledge chunks from the mocked API endpoint.
    """
    url = "http://dummy.local/retrieve"
    payload = {
        "decision": decision
    }
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
    
    try:
        logging.info(f"Calling API {url} with decision: {decision}")
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                body = response.read().decode('utf-8')
                result = json.loads(body)
                return result.get("results", [])
            else:
                logging.error(f"API returned status {response.status}")
                return []
    except urllib.error.URLError as e:
        logging.error(f"Failed to reach knowledge API: {e}")
        logging.warning("Ensure Requestly mock is active and intercepting http://dummy.local/retrieve")
        return []
    except Exception as e:
        logging.error(f"Unexpected error during retrieval: {e}")
        return []

def main():
    # 1. Load Alert Data
    logging.info("Loading alert trace...")
    alert_trace_path = "post_decision_trace.json"
    alert_data = load_json_file(alert_trace_path)
    
    if not alert_data:
        logging.error("Failed to load alert trace. Exiting.")
        return

    # 2. Extract Alert Details
    trace = alert_data.get('input_trace', {})
    decision = trace.get('decision', 'Unknown Issue')
    observed = trace.get('observed_behavior', 'anomaly')
    
    logging.info(f"Processing Alert: {decision}")
    logging.info(f"Observed: {observed}")

    # 3. Retrieve Context from API
    relevant_docs = retrieve_knowledge_from_api(decision)
    
    logging.info(f"Retrieved {len(relevant_docs)} relevant context records.")

    # 4. Format Context
    context_text = ""
    references = set()
    for idx, doc in enumerate(relevant_docs, 1):
        context_text += f"Source {idx}:\n{doc.get('text', 'No text')}\n---\n"
        if 'source' in doc:
             references.add(doc['source'])
        elif 'metadata' in doc and 'document' in doc['metadata']:
            references.add(doc['metadata']['document'])

    reference_str = ", ".join(references) if references else "Internal Knowledge Base"

    # 5. Generate Recommendation (Using Groq or Mock)
    output_data = {}
    
    # Try to use Groq if available
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("\n" + "="*40)
        print(" [!] GROQ_API_KEY not found. Simulating structured JSON Output.")
        print("="*40)
        
        # Simulated JSON content if LLM is unavailable
        # We try to use the retrieved text if available, otherwise generic fallback
        rec_actions = []
        if relevant_docs:
             # Basic extraction for fallback
             rec_actions.append(f"Based on KB: {relevant_docs[0].get('text', '')[:100]}...")
        else:
             rec_actions = [
                f"Address {decision}: Check lubrication levels immediately.",
                "Schedule bearing replacement within 5–10 days if symptoms persist.",
                f"Monitor {observed} and vibration trends closely."
            ]

        output_data = {
            "recommended_action": rec_actions,
            "safety_note": "Before inspecting equipment, ensure power is isolated and lock-out/tag-out procedures are followed.",
            "reference": reference_str
        }
    else:
        try:
            from langchain_groq import ChatGroq
            chat = ChatGroq(temperature=0, model_name="llama-3.3-70b-versatile", groq_api_key=api_key)
            
            json_prompt = f"""
            You are an expert industrial maintenance assistant.
            
            ALERT: {decision} with {observed}
            CONTEXT: {context_text}
            
            TASK: Return a valid JSON object with the following structure:
            {{
              "recommended_action": ["action 1", "action 2", ...],
              "safety_note": "safety warning...",
              "reference": "source names..."
            }}
            
            Strictly return ONLY the JSON string.
            """
            
            response = chat.invoke(json_prompt)
            content = response.content.strip()
            # clean up potential markdown fencing
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            
            output_data = json.loads(content.strip())
            
        except Exception as e:
            logging.error(f"Error calling LLM or parsing JSON: {e}")
            output_data = {
                "error": "Failed to generate recommendation via LLM",
                "recommended_action": ["Consult manual manually"],
                "safety_note": "Exercise caution",
                "reference": "N/A"
            }

    # 6. Save Logic
    output_file = "final_recommendation.json"
    print(f"\nFinal Structure:\n{json.dumps(output_data, indent=2)}")
    
    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\nSaved output to {output_file}")

if __name__ == "__main__":
    main()

