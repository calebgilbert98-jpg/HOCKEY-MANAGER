#!/usr/bin/env python3

# Read the file
with open('windows.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace all remaining instances
content = content.replace(
    'f"{p.full_name} ({p.overall_rating()})"',
    'f"{p.full_name} ({p.primary_position.value}) - {p.overall_rating()}"'
)

content = content.replace(
    'f"{player.full_name} ({player.overall_rating()})"',
    'f"{player.full_name} ({player.primary_position.value}) - {player.overall_rating()}"'
)

# Write the file back
with open('windows.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("All player name formats updated successfully!")
