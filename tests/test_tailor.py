#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
import tailor_agent

result = tailor_agent.run(job_url="https://www.databricks.com/company/careers/field-engineering---fe-invested-dsa/delivery-solutions-architect-8452394002")

print("Status:", result.get("status"))
if result.get("status") == "completed":
    print("PDF:", result.get("pdf_file"))
    print("Cover letter:", result.get("cover_letter_file"))
else:
    print("Reason:", result.get("reason"))
