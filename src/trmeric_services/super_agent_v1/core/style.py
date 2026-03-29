TABLE_CSS = """
table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}
th, td {
  border: 1px solid #ccc;
  padding: 6px 8px;
  vertical-align: top;
  word-wrap: break-word;
}
th {
  background: #f5f5f5;
  font-weight: bold;
}
"""


def inject_css(html: str, css: str) -> str:
    if "</head>" in html:
        return html.replace(
            "</head>",
            f"<style>{css}</style></head>"
        )
    return f"<style>{css}</style>{html}"
