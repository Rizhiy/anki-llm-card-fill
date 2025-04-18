import json
import re
from typing import Mapping

from .html_to_markdown import html_to_markdown


def parse_field_mappings(field_mappings_text: str) -> dict[str, str]:
    """Parse the field mappings text into a dictionary."""
    result = {}
    if not field_mappings_text.strip():
        return result

    # Split by lines and filter empty lines
    lines = [line.strip() for line in field_mappings_text.split("\n") if line.strip()]

    for line in lines:
        # Find the first colon that separates field name from description
        parts = line.split(":", 1)
        if len(parts) == 2:
            field_name = parts[0].strip()
            field_description = parts[1].strip()
            result[field_name] = field_description

    return result


def construct_prompt(template: str, field_mappings: dict[str, str], card_fields: Mapping[str, str]) -> str:
    """Construct a prompt by filling in field values and adding field descriptions."""
    # Replace field references in the template
    prompt = template
    for field_name, field_value in card_fields.items():
        placeholder = "{" + field_name + "}"
        # Convert HTML to Markdown for better prompt readability
        md_value = html_to_markdown(field_value)
        prompt = prompt.replace(placeholder, md_value)

    # Add field mapping instructions
    prompt += "\n\nPlease generate content for these fields:\n"
    for field_name, description in field_mappings.items():
        prompt += f"\n- {field_name}: {description}"

    # Add JSON formatting instructions
    prompt += "\n\nProvide your response in JSON format with field names as keys. For example:\n"
    prompt += "{\n"
    example_fields = list(field_mappings.keys())[:2] if len(field_mappings) > 1 else list(field_mappings.keys())
    for field in example_fields:
        prompt += f'  "{field}": "Content for {field}",\n'
    prompt += "  ...\n}"
    prompt += "\nYour response should be a valid JSON, so I can parse it directly."
    prompt += "\nThe response should contain only one combination."

    return prompt


def parse_llm_response(response: str) -> dict[str, str]:
    """Extract JSON from the LLM response and parse it."""
    # Try to find JSON content in the response
    json_pattern = r"\{[\s\S]*\}"
    json_match = re.search(json_pattern, response)

    if json_match:
        try:
            json_str = json_match.group(0)
            return json.loads(json_str)
        except json.JSONDecodeError:
            return {"error": f"Failed to parse JSON from response:\n{response}"}

    return {"error": "No JSON found in response"}
