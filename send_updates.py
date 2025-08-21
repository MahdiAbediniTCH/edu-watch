import json
import requests
from decouple import config

# Load Telegram bot token
TELEGRAM_TOKEN = config("TELEGRAM_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

# Private channel numeric ID (note the negative and 100 prefix)
CHANNEL_ID = -1002910685507

# Files
CURRENT_FILE = "courses_output.json"
OLD_FILE = "courses_output - old.json"

# ----- JSON comparison -----
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def compare_courses(old_data, new_data):
    old_keys = set(old_data.keys())
    new_keys = set(new_data.keys())

    added_keys = new_keys - old_keys
    removed_keys = old_keys - new_keys
    common_keys = old_keys & new_keys

    def group_by_department(keys, source_data):
        grouped = {}
        for k in keys:
            dept = source_data[k].get("Department", "Unknown")
            if dept not in grouped:
                grouped[dept] = {}
            grouped[dept][k] = source_data[k]
        return grouped

    added = group_by_department(added_keys, new_data)
    removed = group_by_department(removed_keys, old_data)

    # For updated, only store the changed fields
    updated_temp = {}
    for k in common_keys:
        if new_data[k] != old_data[k]:
            changes = {}
            for field in new_data[k]:
                if field in old_data[k] and new_data[k][field] != old_data[k][field]:
                    changes[field] = {"old": old_data[k][field], "new": new_data[k][field]}
            if changes:
                updated_temp[k] = {"changes": changes, "Department": new_data[k].get("Department", "Unknown")}

    # Group updates by department
    updated = {}
    for k, val in updated_temp.items():
        dept = val["Department"]
        if dept not in updated:
            updated[dept] = {}
        updated[dept][k] = val["changes"]

    return added, removed, updated

def format_message(added, removed, updated):
    messages = []

    def format_grouped(grouped_data, title, emoji):
        if not grouped_data:
            return
        messages.append(f"{emoji} {title}:")
        for dept, courses in grouped_data.items():
            messages.append(f"\n🏛️ {dept}:")
            for k, info in courses.items():
                if isinstance(info, dict) and "changes" in info:
                    # Shouldn't happen now, but just in case
                    info = info["changes"]
                if title == "Updated Courses":
                    lines = [f"- {k}:"]
                    for field, vals in info.items():
                        lines.append(f"    {field}: {vals['old']} -> {vals['new']}")
                    messages.append("\n".join(lines))
                else:
                    messages.append(f"- {info.get('Name', 'Unnamed')} (ID: {k})")

    format_grouped(added, "Added Courses", "🟢")
    format_grouped(removed, "Removed Courses", "🔴")
    format_grouped(updated, "Updated Courses", "🟡")

    return "\n".join(messages)

# ----- Telegram sending -----
MAX_LENGTH = 4000  # safe margin below 4096

def send_telegram_message(text):
    # Split text into chunks if too long
    chunks = []
    while text:
        if len(text) <= MAX_LENGTH:
            chunks.append(text)
            break
        # try to split at newline for readability
        split_pos = text.rfind("\n", 0, MAX_LENGTH)
        if split_pos == -1:
            split_pos = MAX_LENGTH
        chunks.append(text[:split_pos])
        text = text[split_pos:].lstrip("\n")
    
    for chunk in chunks:
        payload = {"chat_id": CHANNEL_ID, "text": chunk}
        response = requests.post(TELEGRAM_API_URL, json=payload)
        response.raise_for_status()

# ----- Main function -----
def main():
    old_data = load_json(OLD_FILE)
    new_data = load_json(CURRENT_FILE)

    added, removed, updated = compare_courses(old_data, new_data)
    if not (added or removed or updated):
        return  # No changes — do not send anything

    message = format_message(added, removed, updated)
    send_telegram_message(message)

if __name__ == "__main__":
    main()