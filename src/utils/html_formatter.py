import re

def clean_html(html_content):
    cleaned_html = re.sub(r'```html|```', '', html_content).strip()
    # Replace all heading tags (h1, h2, h3, ...) with h4
    cleaned_html = re.sub(r'<h[1-6]>', '<h4>', cleaned_html)
    cleaned_html = re.sub(r'</h[1-6]>', '</h4>', cleaned_html)
    # Wrap the cleaned content inside an outer div
    wrapped_html = f'<div>\n{cleaned_html}\n</div>'
    return wrapped_html
