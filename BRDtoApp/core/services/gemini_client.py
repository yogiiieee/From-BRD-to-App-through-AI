# core/services/gemini_client.py
import string
import json
import logging
from django.conf import settings
import os
import re
import requests

from django.conf import settings
from django.utils.text import slugify

logger = logging.getLogger(__name__)

# --- Gemini API Configuration ---
# DELETE THIS LINE: GEMINI_API_KEY = settings.GEMINI_API_KEY
# The GEMINI_API_KEY will now be accessed directly from `settings.GEMINI_API_KEY` inside functions.

GEMINI_MODEL_NAME = "gemini-1.5-flash" 
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL_NAME}:generateContent"

# --- Helper to load prompt templates ---
def load_prompt_template(template_name):
    """Loads a prompt template from the prompts directory."""
    template_path = os.path.join(settings.BASE_DIR, 'core', 'prompts', template_name)
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Prompt template not found: {template_path}")
        return ""

# --- Helper to extract JSON from AI's markdown response ---
def _extract_json_from_markdown(text_content):
    """
    More robust JSON extractor that handles:
    - Multiple JSON objects
    - Markdown wrappers
    - Trailing garbage
    """
    logger.debug(f"Raw AI response text: {text_content[:200]}...")
    
    # First try direct JSON parse
    try:
        result = json.loads(text_content.strip())
        logger.debug(f"Successfully parsed direct JSON: {result}")
        return result
    except json.JSONDecodeError:
        logger.debug("Direct JSON parse failed, trying other methods...")
    
    # Try extracting from markdown code blocks
    json_candidates = re.findall(r'(?s)```(?:json)?\n(.*?)\n```', text_content)
    for candidate in json_candidates:
        try:
            result = json.loads(candidate.strip())
            logger.debug(f"Successfully extracted from markdown: {result}")
            return result
        except json.JSONDecodeError:
            logger.debug("Markdown JSON extraction failed for candidate")
            continue
    
    # Try finding JSON-like objects without markdown
    json_like = re.search(r'\{.*?\}', text_content)
    if json_like:
        try:
            result = json.loads(json_like.group(0))
            logger.debug(f"Successfully extracted from text: {result}")
            return result
        except json.JSONDecodeError:
            logger.debug("Text JSON extraction failed")
            pass
    
    # If all else fails, try to clean up the text and parse again
    cleaned = re.sub(r'[^\{\}\[\]\:\,\"\w\s]', '', text_content)
    try:
        result = json.loads(cleaned.strip())
        logger.debug(f"Successfully parsed cleaned text: {result}")
        return result
    except json.JSONDecodeError as e:
        logger.error(f"Could not extract valid JSON: {str(e)}")
        logger.error(f"Raw text content: {text_content[:500]}...")
        raise ValueError(f"Could not extract valid JSON: {str(e)}")

# --- Core AI Interaction Function ---
def generate_text(prompt_content, parse_json=True):
    """
    Sends a prompt to the Gemini model via API and returns the response.
    
    Args:
        prompt_content (str): The prompt to send to the model
        parse_json (bool): Whether to try parsing the response as JSON
    
    Returns:
        dict: The parsed JSON response if parse_json=True, otherwise raw text
    
    Raises:
        ValueError: If API key is not configured
        requests.exceptions.RequestException: If API request fails
        json.JSONDecodeError: If response parsing fails
    """
    # Verify API key is configured and valid
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        logger.error("Gemini API key is not configured in settings")
        raise ValueError("Gemini API key is not configured. Please set GEMINI_API_KEY in your environment variables")

    # Log API key length (without showing actual key)
    logger.info(f"Using Gemini API key of length: {len(api_key)}")

    # Test if API key is properly formatted
    if not api_key.startswith('AIzaSy'):
        logger.error("Gemini API key does not appear to be in the correct format")
        raise ValueError("Invalid Gemini API key format. Expected key to start with 'AIzaSy'")

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }

    # Add API key to URL as query parameter as an alternative method
    api_url = f"{GEMINI_API_URL}?key={api_key}"

    data = {
        'contents': [{'parts': [{'text': prompt_content}]}]
    }
    
    try:
        logger.debug(f"Sending request to Gemini API with prompt length: {len(prompt_content)}")
        # Try with both authentication methods
        try:
            # First try with Authorization header
            response = requests.post(GEMINI_API_URL, headers=headers, json=data)
            logger.debug(f"Response status code (header auth): {response.status_code}")
            response.raise_for_status()
            logger.info("Successfully authenticated with header method")
        except requests.exceptions.HTTPError:
            # If header method fails, try with API key in URL
            logger.info("Header authentication failed, trying URL parameter method...")
            response = requests.post(api_url, headers={'Content-Type': 'application/json'}, json=data)
            logger.debug(f"Response status code (URL auth): {response.status_code}")
            response.raise_for_status()
            logger.info("Successfully authenticated with URL parameter method")
        
        response_data = response.json()
        logger.debug(f"Raw response data: {response_data}")
        
        # Extract the actual content from Gemini's response structure
        text_content = response_data['candidates'][0]['content']['parts'][0]['text']
        logger.debug(f"Extracted text content: {text_content[:200]}...")
        
        if parse_json:
            result = _extract_json_from_markdown(text_content)
            logger.debug(f"Parsed JSON result: {result}")
            return result
        else:
            return text_content
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Gemini API request failed: {str(e)}", exc_info=True)
        logger.error(f"Full response: {response.text if 'response' in locals() else 'No response'}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini response as JSON: {str(e)}", exc_info=True)
        logger.error(f"Response text: {response.text if 'response' in locals() else 'No response'}")
        raise
        logger.error(f"Failed to decode API response JSON: {json_e}", exc_info=True)
        return {'error': True, 'message': f"Malformed JSON from AI API: {json_e}", 'raw_ai_response': response.text if 'response' in locals() else 'N/A'}
    except Exception as e:
        logger.error(f"An unexpected error occurred during AI API call: {e}", exc_info=True)
        return {'error': True, 'message': f"An unexpected error occurred during AI API call: {e}", 'raw_ai_response': str(e)}

    if parse_json:
        try:
            return _extract_json_from_markdown(raw_ai_response_text)
        except ValueError as e:
            logger.error(f"Failed to parse JSON from AI's text response (expected JSON): {e}")
            return {'error': True, 'message': f"AI returned invalid JSON: {e}", 'raw_ai_response': raw_ai_response_text}
    else:
        return raw_ai_response_text

# --- Gemini Client Interface Functions (unchanged - they call generate_text) ---

def analyze_brd(brd_content):
    """Analyzes BRD content using a prompt and returns structured JSON."""
    try:
        base_template_raw = load_prompt_template('base_prompt.txt')
        brd_analysis_template_raw = load_prompt_template('brd_analysis_prompt.txt')

        intermediate_prompt = brd_analysis_template_raw.replace(
            '{base_prompt_content}', base_template_raw
        )
        
        final_prompt = intermediate_prompt.format(
            parsed_text=brd_content
        )
        
        logger.info("Sending BRD analysis prompt to AI...")
        structured_data = generate_text(final_prompt, parse_json=True)

        if structured_data and structured_data.get('error'):
            return structured_data
            
        return {'status': 'success', 'analysis_data': structured_data, 'raw_ai_response': json.dumps(structured_data), 'extracted_text': brd_content}
    except Exception as e:
        logger.error(f"Error during BRD analysis: {e}", exc_info=True)
        return {'status': 'error', 'message': f"Failed to analyze BRD due to an internal processing error: {e}", 'raw_ai_response': str(e)}

def identify_tech_stack(analysis_data):
    """
    Identifies the tech stack based on BRD analysis data.
    
    Args:
        analysis_data (str): JSON string containing BRD analysis data
        
    Returns:
        dict: Parsed JSON response with tech stack information
        
    Raises:
        ValueError: If API key is not configured or response parsing fails
    """
    logger.info("Starting tech stack identification...")
    
    # Load the tech stack identification prompt template
    base_prompt = load_prompt_template('base_prompt.txt')
    tech_stack_prompt = load_prompt_template('tech_stack_identification_prompt.txt')
    
    if not base_prompt or not tech_stack_prompt:
        logger.error("Failed to load required prompt templates")
        raise ValueError("Failed to load required prompt templates")
    
    try:
        # Combine prompts with analysis data
        full_prompt = tech_stack_prompt.replace(
            '{{ ... }}', ''
        ).replace(
            '{{base_prompt_content}}', base_prompt
        ).replace(
            '{{analysis_data_json}}', json.dumps(analysis_data, indent=2)
        )
        
        logger.debug(f"Tech stack prompt length: {len(full_prompt)} characters")
        logger.debug(f"First 500 chars of prompt: {full_prompt[:500]}")
        
        # Generate response
        raw_response = generate_text(full_prompt, parse_json=False)  # Get raw text first
        logger.debug(f"Raw AI response: {raw_response[:500]}...")
        
        # Try multiple JSON parsing strategies
        try:
            # First try direct JSON parse
            response = json.loads(raw_response.strip())
            logger.debug("Successfully parsed direct JSON")
        except json.JSONDecodeError:
            logger.debug("Direct JSON parse failed, trying markdown extraction...")
            # Try extracting from markdown code blocks
            json_candidates = re.findall(r'(?s)```(?:json)?\n(.*?)\n```', raw_response)
            for candidate in json_candidates:
                try:
                    response = json.loads(candidate.strip())
                    logger.debug("Successfully extracted from markdown")
                    break
                except json.JSONDecodeError:
                    logger.debug("Markdown JSON extraction failed for candidate")
                    continue
            else:  # If no valid JSON found in code blocks
                logger.debug("No valid JSON found in code blocks, trying text extraction...")
                # Try finding JSON-like objects without markdown
                json_like = re.search(r'\{.*?\}', raw_response)
                if json_like:
                    try:
                        response = json.loads(json_like.group(0))
                        logger.debug("Successfully extracted from text")
                    except json.JSONDecodeError:
                        logger.debug("Text JSON extraction failed")
                        raise ValueError("No valid JSON found in response")
                else:
                    raise ValueError("No JSON-like content found in response")
        
        # Validate response structure
        if not isinstance(response, dict):
            raise ValueError("AI response is not a dictionary")
            
        frontend_tech = response.get('frontend', {})
        backend_tech = response.get('backend', {})

        logger.info(f"Identified tech stack: Frontend={frontend_tech}, Backend={backend_tech}")
        
        ans= {
            'status': 'success',
            'tech_stack': {
                'frontend': frontend_tech,
                'backend': backend_tech
            },
            'raw_ai_response': json.dumps(response)
        }
        print(ans)
        return ans
    except json.JSONDecodeError as je:
        logger.error(f"Failed to decode AI response: {je}")
        return {
            'status': 'error',
            'message': "AI returned invalid JSON format",
            'raw_ai_response': str(je)
        }
    except ValueError as ve:
        logger.error(f"Validation error: {ve}")
        return {
            'status': 'error',
            'message': str(ve),
            'raw_ai_response': json.dumps(tech_stack_response) if 'tech_stack_response' in locals() else 'N/A'
        }
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return {
            'status': 'error',
            'message': f"Unexpected error during tech stack identification: {str(e)}",
            'raw_ai_response': str(e)
        }


def generate_code_for_task(project_summary, identified_tech_stack, user_story_context, task_description):
    """
    Generates code for a specific task based on project context and tech stack.
    """
    try:
        base_template_raw = load_prompt_template('base_prompt.txt')
        code_gen_template_raw = load_prompt_template('code_generation_task_prompt.txt')

        intermediate_prompt = code_gen_template_raw.replace(
            '{base_prompt_content}', base_template_raw
        )

        final_prompt = intermediate_prompt.format(
            project_summary=project_summary,
            identified_tech_stack_json=json.dumps(identified_tech_stack, indent=2),
            user_story_json=json.dumps(user_story_context, indent=2),
            task_description=task_description
        )
        
        logger.info(f"Generating code for task: {task_description}")
        raw_code_content_or_error = generate_text(final_prompt, parse_json=False)

        if isinstance(raw_code_content_or_error, dict) and raw_code_content_or_error.get('error'):
            return raw_code_content_or_error

        raw_code_content = raw_code_content_or_error

        file_path = "generated_code/unknown_file.txt"
        language = "plaintext"

        task_lower = task_description.lower()
        frontend_tech = identified_tech_stack.get('frontend', '').lower()
        backend_tech = identified_tech_stack.get('backend', '').lower()

        if "react" in frontend_tech and ("component" in task_lower or "ui" in task_lower or "form" in task_lower):
            language = "javascript"
            component_name_match = re.search(r'(?:create|build|develop|implement)\s+(.+?)\s+(?:component|form|ui|page)', task_lower)
            component_name = "GenericComponent"
            if component_name_match:
                slugged_name = slugify(component_name_match.group(1).strip())
                component_name = "".join(word.capitalize() for word in slugged_name.split('-'))
            elif user_story_context.get('title'):
                story_title_slug = slugify(user_story_context['title'].replace('as a', '').replace('i want to', '').replace('so that', ''))
                component_name = "".join(word.capitalize() for word in story_title_slug.split('-') if word)
            file_path = f"frontend/src/components/{component_name}.jsx"
            
        elif "django" in backend_tech and ("model" in task_lower or "database" in task_lower or "schema" in task_lower):
            language = "python"
            model_name_match = re.search(r'(?:create|define|implement)\s+(.+?)\s+(?:model|table|schema)', task_lower)
            model_name = "GenericModel"
            if model_name_match:
                slugged_name = slugify(model_name_match.group(1).strip())
                model_name = "".join(word.capitalize() for word in slugged_name.split('-'))
            elif user_story_context.get('title'):
                story_title_slug = slugify(user_story_context['title'].replace('as a', '').replace('i want to', '').replace('so that', ''))
                model_name = "".join(word.capitalize() for word in story_title_slug.split('-') if word)
            file_path = f"backend/app_name/models/{model_name}.py" 
            
        elif "node.js" in backend_tech and ("api endpoint" in task_lower or "route" in task_lower or "server" in task_lower):
            language = "javascript"
            endpoint_name_match = re.search(r'(?:implement|create|develop)\s+(.+?)\s+(?:api endpoint|route)', task_lower)
            endpoint_name = "generic_route"
            if endpoint_name_match:
                endpoint_name = slugify(endpoint_name_match.group(1).strip())
            file_path = f"backend/routes/{endpoint_name}.js"
            
        elif "html" in frontend_tech and ("page" in task_lower or "html" in task_lower or "markup" in task_lower):
            language = "html"
            page_name_match = re.search(r'(?:create|develop)\s+(.+?)\s+(?:page|html)', task_lower)
            page_name = "generic_page"
            if page_name_match:
                page_name = slugify(page_name_match.group(1).strip())
            file_path = f"frontend/{page_name}.html"


        return {
            'file_path': file_path,
            'content': raw_code_content,
            'language': language
        }

    except Exception as e:
        logger.error(f"Error generating code for task '{task_description}': {e}", exc_info=True)
        return {
            'error': True,
            'details': f"Failed to generate code: {e}",
            'task_description': task_description,
            'raw_ai_response': locals().get('raw_code_content', 'N/A')
        }

def validate_tech_stack_response(response):
    """Validates the structure of tech stack responses"""
    required_keys = {'frontend', 'backend'}
    if not isinstance(response, dict):
        raise ValueError("Response must be a dictionary")
    
    if not required_keys.issubset(response.keys()):
        missing = required_keys - set(response.keys())
        raise ValueError(f"Missing required keys: {missing}")
    
    if not all(isinstance(v, str) for v in response.values()):
        raise ValueError("All values must be strings")
    
    # Additional content validation
    invalid_values = [
        value.lower() for value in response.values() 
        if value.lower() in ('', 'null', 'undefined', 'unspecified')
    ]
    if invalid_values:
        raise ValueError(f"Invalid technology values: {invalid_values}")
    
    return response