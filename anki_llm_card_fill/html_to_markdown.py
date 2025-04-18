"""Simple HTML to Markdown converter for Anki card fields without external dependencies."""

import html
import re


def html_to_markdown(html_text: str) -> str:
    """Convert HTML to Markdown, focusing only on basic formatting.

    Args:
        html_text: HTML content from an Anki card field

    Returns:
        Markdown formatted string
    """
    if not html_text or html_text.isspace():
        return ""

    # Unescape HTML entities first
    text = html.unescape(html_text)

    # Handle basic formatting with simple replacements
    # Bold
    text = re.sub(r"<b>(.*?)</b>", r"**\1**", text, flags=re.DOTALL)
    text = re.sub(r"<strong>(.*?)</strong>", r"**\1**", text, flags=re.DOTALL)

    # Italic
    text = re.sub(r"<i>(.*?)</i>", r"*\1*", text, flags=re.DOTALL)
    text = re.sub(r"<em>(.*?)</em>", r"*\1*", text, flags=re.DOTALL)

    # Line breaks
    text = re.sub(r"<br\s*/?>|<br\s*>", "\n", text)

    # Process lists
    text = convert_lists(text)

    # Clean up whitespace - only collapse multiple spaces, preserve line breaks
    text = re.sub(r" +", " ", text)

    return text.strip()


def convert_lists(html_text: str) -> str:
    """Convert HTML lists to Markdown format.

    This function only handles basic ul/ol/li elements without complex nesting.

    Args:
        html_text: HTML content with possible list elements

    Returns:
        Text with lists converted to Markdown
    """
    result = html_text

    # Process unordered lists
    ul_pattern = r"<ul>(.*?)</ul>"
    for ul_match in re.finditer(ul_pattern, html_text, re.DOTALL):
        ul_content = ul_match.group(1)
        md_list = process_list_items(ul_content, "*")
        result = result.replace(ul_match.group(0), md_list)

    # Process ordered lists
    ol_pattern = r"<ol>(.*?)</ol>"
    for ol_match in re.finditer(ol_pattern, html_text, re.DOTALL):
        ol_content = ol_match.group(1)
        md_list = process_list_items(ol_content, "1.")
        result = result.replace(ol_match.group(0), md_list)

    return result


def process_list_items(list_html: str, marker: str) -> str:
    """Convert HTML list items to Markdown list items.

    Args:
        list_html: HTML content inside a list tag
        marker: List marker to use (* for ul, 1. for ol)

    Returns:
        Markdown formatted list
    """
    lines = []
    li_pattern = r"<li>(.*?)</li>"

    for i, li_match in enumerate(re.finditer(li_pattern, list_html, re.DOTALL)):
        item_content = li_match.group(1).strip()

        # For ordered lists, use incrementing numbers
        current_marker = f"{i + 1}." if marker == "1." and i > 0 else marker

        # Add the item as a separate line
        lines.append(f"{current_marker} {item_content}")

    # Join lines with newlines and add surrounding newlines
    return "\n" + "\n".join(lines) + "\n"
