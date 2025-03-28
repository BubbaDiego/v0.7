import os
import json
from config.config_constants import BASE_DIR, LOG_DATE_FORMAT

def generate_cycle_report():
    """
    Reads the cyclone log file (cyclone_log.txt) from the logs folder,
    builds a summary and detailed table from the JSON log records,
    and writes a pretty HTML report to cycle_report.html in the logs folder.
    """
    logs_dir = os.path.join(BASE_DIR, "logs")
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    cyclone_log_path = os.path.join(logs_dir, "cyclone_log.txt")
    cycle_report_path = os.path.join(logs_dir, "cycle_report.html")

    if not os.path.exists(cyclone_log_path):
        print(f"No cyclone log file found at {cyclone_log_path}. Cannot generate report.")
        return

    log_entries = []
    with open(cyclone_log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                log_entries.append(record)
            except json.JSONDecodeError:
                continue

    summary = {}
    for record in log_entries:
        op_type = record.get("operation_type", "Unknown")
        summary[op_type] = summary.get(op_type, 0) + 1

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Cycle Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f4f4f4;
        }}
        h1, h2 {{
            color: #333;
        }}
        .summary {{
            margin-bottom: 20px;
            background-color: #fff;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            background-color: #fff;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background-color: #333;
            color: white;
        }}
        tr:nth-child(even) {{background-color: #f2f2f2;}}
    </style>
</head>
<body>
    <h1>Cycle Report</h1>
    <div class="summary">
        <h2>Summary</h2>
        <ul>
"""
    for op, count in summary.items():
        html_content += f"            <li><strong>{op}:</strong> {count}</li>\n"
    html_content += """        </ul>
    </div>
    <h2>Detailed Log Entries</h2>
    <table>
        <tr>
            <th>Timestamp</th>
            <th>Operation Type</th>
            <th>Source</th>
            <th>File</th>
            <th>Message</th>
        </tr>
"""
    for record in log_entries:
        ts = record.get("timestamp", "")
        op_type = record.get("operation_type", "")
        source = record.get("source", "")
        file_name = record.get("file", "")
        message = record.get("message", "")
        html_content += f"""        <tr>
            <td>{ts}</td>
            <td>{op_type}</td>
            <td>{source}</td>
            <td>{file_name}</td>
            <td>{message}</td>
        </tr>
"""
    html_content += """    </table>
</body>
</html>
"""

    with open(cycle_report_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Cycle report generated: {cycle_report_path}")
