"""
Agent card served at /.well-known/agent.json.
Describes this agent's identity, capabilities, and skills to other agents.
"""
import os

BASE_URL = os.environ.get("A2A_BASE_URL", "http://localhost:8000")

AGENT_CARD = {
    "name": "Resume Builder Agent",
    "description": (
        "A specialist agent for job application workflows. "
        "Tailors resumes to job descriptions, searches LinkedIn for matching jobs, "
        "and analyses LinkedIn profiles against a resume to identify gaps."
    ),
    "url": BASE_URL,
    "version": "1.0.0",
    "documentationUrl": f"{BASE_URL}/docs",
    "capabilities": {
        "streaming": True,
        "pushNotifications": False,
        "stateTransitionHistory": False,
    },
    "authentication": {
        "schemes": ["Bearer"],
    },
    "defaultInputModes": ["text"],
    "defaultOutputModes": ["text"],
    "skills": [
        {
            "id": "tailor_resume",
            "name": "Tailor Resume to Job Description",
            "description": (
                "Takes a job description (text or URL) and produces a tailored resume PDF "
                "and cover letter, with humanised writing and no AI tells."
            ),
            "tags": ["resume", "cover-letter", "tailoring", "job-application"],
            "examples": [
                "Tailor my resume to this job description: [paste JD here]",
                "Tailor my resume to: https://linkedin.com/jobs/view/1234567890/",
            ],
            "inputModes": ["text"],
            "outputModes": ["text", "file"],
        },
        {
            "id": "search_jobs",
            "name": "Search LinkedIn Jobs",
            "description": (
                "Searches LinkedIn for jobs matching the candidate's resume. "
                "Returns a ranked list of relevant openings with match reasons."
            ),
            "tags": ["jobs", "linkedin", "search", "matching"],
            "examples": [
                "Find relevant jobs for me on LinkedIn",
                "Search for new jobs matching my profile",
            ],
            "inputModes": ["text"],
            "outputModes": ["text"],
        },
        {
            "id": "analyse_linkedin",
            "name": "Analyse LinkedIn Profile",
            "description": (
                "Compares the candidate's LinkedIn profile against their resume "
                "and generates specific, prioritised update recommendations."
            ),
            "tags": ["linkedin", "profile", "optimisation"],
            "examples": [
                "Analyse my LinkedIn profile and tell me what to update",
                "Compare my LinkedIn profile to my resume",
            ],
            "inputModes": ["text"],
            "outputModes": ["text"],
        },
    ],
}
