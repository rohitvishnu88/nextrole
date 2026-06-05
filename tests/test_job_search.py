#!/usr/bin/env python3
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
import job_search_agent

resume = json.load(open('data/resume_data.json'))
result = job_search_agent.run(resume, include_seen=False)

print(f"\nFound {result['total_jobs']} jobs ({result['new_jobs']} new):\n")
for i, job in enumerate(result['jobs'], 1):
    score = job.get('relevance_score', '?')
    print(f"{i}. [{score}/10] {job['title']} at {job['company']} ({job['location']})")
    print(f"   {job.get('match_reason', '')}")
    print(f"   {job.get('url', '')}\n")
