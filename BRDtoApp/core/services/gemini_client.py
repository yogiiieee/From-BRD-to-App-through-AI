# core/services/gemini_client.py
import google.generativeai as genai
import os
import logging
import json # For JSONDecodeError handling
import re # For markdown stripping

logger = logging.getLogger(__name__)

# Ensure your .env is loaded in settings.py before this runs
try:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
except KeyError:
    logger.error("GEMINI_API_KEY environment variable not set. Please set it in your .env file or environment.")
    raise EnvironmentError("GEMINI_API_KEY not found.")

# You might want to experiment with different models:
# gemini-1.5-flash is faster and cheaper, good for rapid iteration/testing
# gemini-1.5-pro is generally more capable and better for complex code generation
# model = genai.GenerativeModel("gemini-1.5-flash")
model = genai.GenerativeModel("gemini-1.5-pro") # Recommended for code generation tasks

def load_prompt_template(template_name):
    """Loads a prompt template from the core/prompts directory."""
    # This path is relative to the current file (gemini_client.py)
    current_dir = os.path.dirname(__file__)
    prompt_path = os.path.join(current_dir, '../prompts', template_name)
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Prompt template not found: {prompt_path}")
        raise ValueError(f"Prompt template '{template_name}' not found.")

def _extract_json_from_markdown(text_with_markdown):
    """
    Extracts a JSON string from a markdown code block (```json).
    Handles cases where AI might include conversational text before/after.
    """
    match = re.search(r'```json\n(.*?)\n```', text_with_markdown, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text_with_markdown.strip() # Fallback if no markdown block

def generate_text(prompt, parse_json=False):
    """
    Sends a prompt to the Gemini model and returns the response text.
    Optionally extracts and parses JSON if parse_json is True.
    """
    try:
        response = model.generate_content(prompt)
        raw_text = response.text

        if parse_json:
            json_string = _extract_json_from_markdown(raw_text)
            try:
                return json.loads(json_string)
            except json.JSONDecodeError as json_e:
                logger.error(f"JSON Decode Error after markdown strip: {json_e}. Raw AI text: {raw_text}")
                # You might want to return an error dictionary or re-raise
                return {"error": "JSON_PARSE_ERROR", "details": str(json_e), "raw_ai_response": raw_text}
        
        return raw_text # Return raw text if not parsing JSON

    except Exception as e:
        logger.error(f"Error generating content from Gemini: {e}", exc_info=True)
        return f"AI generation failed: {e}"

def analyze_brd(parsed_text):
    """
    Analyzes BRD text and returns structured JSON data.
    """
    # Load the base BRD analysis prompt template
    prompt_template = load_prompt_template('brd_analysis_prompt.txt') 

    # Format the prompt with the BRD content
    prompt = prompt_template.format(parsed_text=parsed_text)
    
    # Use generate_text and instruct it to parse JSON
    # This function expects pure JSON and should not have markdown wrappers
    # Modify your `brd_analysis_prompt.txt` to explicitly tell the AI:
    # "Your entire response MUST be a valid JSON object. Do NOT include any text before or after the JSON. Do NOT include markdown code block delimiters (```json)."
    analysis_data = generate_text(prompt, parse_json=True)
    return analysis_data