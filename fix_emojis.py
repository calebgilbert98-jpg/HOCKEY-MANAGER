#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Fix emoji encoding issues in main.py
import re

print("Reading main.py...")
with open('main.py', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

print("Before fix:")
lines = content.split('\n')
for i, line in enumerate(lines[2710:2720], 2710):
    if 'Calendar' in line or 'Finances' in line:
        print(f"Line {i}: {repr(line)}")

# Fix the problematic emojis
content = re.sub(r'"[^"]*Calendar":', '"🗓️ Calendar":', content)
content = re.sub(r'"[^"]*Finances":', '"💰 Finances":', content)

print("\nAfter fix:")
lines = content.split('\n')
for i, line in enumerate(lines[2710:2720], 2710):
    if 'Calendar' in line or 'Finances' in line:
        print(f"Line {i}: {repr(line)}")

print("\nWriting corrected main.py...")
with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fix complete!")
