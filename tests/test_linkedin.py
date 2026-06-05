#!/usr/bin/env python3
import json, sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
import linkedin_agent

print("API key:", os.environ.get('ANTHROPIC_API_KEY', 'NOT SET')[:15])
resume = json.load(open('data/resume_data.json'))
result = linkedin_agent.run(resume)
print('Status:', result.get('status'))
updates = result.get('updates', {})
print()
print('Headline:', updates.get('headline', {}).get('suggested', ''))
print()
print('Summary:', updates.get('summary', {}).get('suggested', '')[:400])
print()
print('Priority actions:')
for a in updates.get('priority_actions', []):
    print(' -', a)
print()
print('Missing skills:', updates.get('missing_skills', []))
