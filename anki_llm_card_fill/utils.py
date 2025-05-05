import json
import re
from typing import Mapping

from aqt.qt import QLineEdit

from .html_to_markdown import html_to_markdown


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


# Source: https://stackoverflow.com/a/47307180/2059584
def set_line_edit_min_width(e: QLineEdit) -> None:
    fm = e.fontMetrics()
    m = e.textMargins()
    c = e.contentsMargins()
    w = fm.horizontalAdvance(e.text()) + m.left() + m.right() + c.left() + c.right()
    e.setMinimumWidth(w + 8)
