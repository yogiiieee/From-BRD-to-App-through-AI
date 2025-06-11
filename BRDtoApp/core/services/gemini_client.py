# core/services/gemini_client.py
import google.generativeai as genai
import os
import logging
import json
import re

logger = logging.getLogger(__name__)

try:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
except KeyError:
    logger.error("GEMINI_API_KEY environment variable not set. Please set it in your .env file or environment.")
    raise EnvironmentError("GEMINI_API_KEY not found.")

model = genai.GenerativeModel("gemini-1.5-flash") # Recommended for code generation, use flash for faster/cheaper iteration

def load_prompt_template(template_name):
    """Loads a prompt template from the core/prompts directory."""
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
    return text_with_markdown.strip()

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
                return {"error": "JSON_PARSE_ERROR", "details": str(json_e), "raw_ai_response": raw_text}
        
        return raw_text

    except Exception as e:
        logger.error(f"Error generating content from Gemini: {e}", exc_info=True)
        return f"AI generation failed: {e}"

# core/services/gemini_client.py (Only the analyze_brd function is changed)

# ... (rest of your gemini_client.py code remains the same: imports, logger, genai.configure, model, load_prompt_template, _extract_json_from_markdown, generate_text) ...

def analyze_brd(parsed_text):
    """
    Analyzes BRD text and returns structured JSON data.
    This function now correctly combines base_prompt.txt and brd_analysis_prompt.txt,
    and uses generate_text's built-in JSON parsing.
    """
    try:
        # 1. Load the raw content of the base prompt
        base_template_raw = load_prompt_template('base_prompt.txt')
        # 2. Load the raw content of the specific BRD analysis prompt template
        # This template still contains {base_prompt_content} AND {parsed_text}
        brd_analysis_template_raw = load_prompt_template('brd_analysis_prompt.txt')

        # 3. First substitution: Inject the base prompt content into the BRD analysis template.
        # We use .replace() here, which is safer when dealing with placeholders
        # that aren't meant to be formatted in the current step.
        # This results in a string that now contains the base prompt content,
        # but still has the '{parsed_text}' placeholder waiting for the next step.
        intermediate_prompt_template = brd_analysis_template_raw.replace(
            '{base_prompt_content}', base_template_raw
        )
        
        # 4. Final substitution: Format the intermediate template with the actual parsed_text.
        # At this point, intermediate_prompt_template only contains the {parsed_text} placeholder.
        final_prompt = intermediate_prompt_template.format(parsed_text=parsed_text)
        
        # 5. Send the fully assembled prompt to Gemini for analysis, expecting JSON.
        analysis_data = generate_text(final_prompt, parse_json=True)
        
        # If generate_text returned an error dictionary, propagate it immediately
        if isinstance(analysis_data, dict) and (analysis_data.get('error') or analysis_data.get('JSON_PARSE_ERROR')):
            return analysis_data # Propagate the error dict directly

        # --- Remaining Validation (if analysis_data is a dict from generate_text) ---
        if not isinstance(analysis_data, dict):
            # This case should ideally not happen if generate_text worked as expected
            # and returned a dict on success or an error dict on failure.
            # But as a safeguard:
            raise ValueError("AI response, after parsing, is not a dictionary as expected.")
            
        # Check for required top-level fields as per your schema
        required_fields = ['project_summary', 'themes']
        for field in required_fields:
            if field not in analysis_data:
                raise ValueError(f"Required field '{field}' missing from AI response JSON.")
                
        # Ensure project_summary is a string (basic type check)
        if not isinstance(analysis_data.get('project_summary'), str):
            raise ValueError("project_summary must be a string in AI response.")
            
        return analysis_data
        
    except Exception as e:
        logger.error(f"Critical error during BRD analysis or prompt assembly: {str(e)}", exc_info=True)
        # Attempt to capture the raw response before the error, if it was generated
        raw_response_for_error = locals().get('raw_response', 'N/A')
        return {
            'error': True,
            'details': f"Failed to analyze BRD due to an internal processing error: {str(e)}",
            'raw_ai_response': raw_response_for_error
        }
