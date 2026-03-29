def formatSQLData(data):
    if not data:
        return "No data available"
    headers = list(data[0].keys())

    # Start and end the header and separator rows with a pipe
    markdown_table = (
        "|"
        + " | ".join(headers)
        + "|\n"
        + "|"
        + "|".join("---" for _ in headers)
        + "|\n"
    )

    # Fill the table with data
    for entry in data:
        row = []
        for header in headers:
            # Check for None and represent it as a space for better readability
            value = entry[header]
            if value is None:
                row.append(" ")
            else:
                # Handle complex data types like lists or dictionaries by converting them to a string
                if isinstance(value, (list, dict)):
                    row.append(
                        f"`{str(value)}`"
                    )  # Use backticks to encapsulate complex data
                else:
                    row.append(str(value))
        # Start and end data rows with a pipe
        markdown_table += "|" + " | ".join(row) + "|\n"

    return markdown_table
