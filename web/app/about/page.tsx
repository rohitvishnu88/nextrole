import Link from "next/link";
import { FileText, Briefcase, Search, Wand2, ArrowRight, Zap, Shield, Globe } from "lucide-react";

function HeroIllustration() {
  return (
    <svg viewBox="0 0 480 320" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
      {/* Background blobs */}
      <circle cx="380" cy="60" r="120" fill="#FFFFFF" opacity="0.6" />
      <circle cx="100" cy="260" r="90" fill="#FFFFFF" opacity="0.5" />

      {/* Resume document */}
      <rect x="60" y="60" width="150" height="200" fill="white" stroke="#D9D7D0" strokeWidth="1.5" />
      <rect x="80" y="90" width="80" height="8" fill="#000000" opacity="0.8" />
      <rect x="80" y="108" width="110" height="5" fill="#5A5A57" opacity="0.4" />
      <rect x="80" y="118" width="90" height="5" fill="#5A5A57" opacity="0.4" />
      <rect x="80" y="138" width="60" height="5" fill="#000000" opacity="0.6" />
      <rect x="80" y="153" width="110" height="4" fill="#5A5A57" opacity="0.3" />
      <rect x="80" y="163" width="100" height="4" fill="#5A5A57" opacity="0.3" />
      <rect x="80" y="173" width="85" height="4" fill="#5A5A57" opacity="0.3" />
      <rect x="80" y="193" width="60" height="5" fill="#000000" opacity="0.6" />
      <rect x="80" y="208" width="110" height="4" fill="#5A5A57" opacity="0.3" />
      <rect x="80" y="218" width="95" height="4" fill="#5A5A57" opacity="0.3" />

      {/* AI sparkle in middle */}
      <circle cx="240" cy="160" r="36" fill="#000000" opacity="0.12" />
      <circle cx="240" cy="160" r="24" fill="#000000" opacity="0.2" />
      <circle cx="240" cy="160" r="14" fill="#000000" />
      {/* Lightning bolt */}
      <path d="M243 152l-5 10h4l-5 10 9-12h-5l6-8z" fill="white" />

      {/* Arrows */}
      <path d="M218 160h-8" stroke="#000000" strokeWidth="2" strokeLinecap="square" />
      <path d="M208 156l-6 4 6 4" stroke="#000000" strokeWidth="2" strokeLinecap="square" strokeLinejoin="miter" />
      <path d="M262 160h8" stroke="#000000" strokeWidth="2" strokeLinecap="square" />
      <path d="M272 156l6 4-6 4" stroke="#000000" strokeWidth="2" strokeLinecap="square" strokeLinejoin="miter" />

      {/* Tailored resume document */}
      <rect x="270" y="60" width="150" height="200" fill="white" stroke="#D9D7D0" strokeWidth="1.5" />
      {/* Accent stripe */}
      <rect x="270" y="60" width="6" height="200" fill="#000000" opacity="0.8" />
      <rect x="290" y="90" width="80" height="8" fill="#000000" opacity="0.8" />
      <rect x="290" y="108" width="110" height="5" fill="#5A5A57" opacity="0.4" />
      <rect x="290" y="118" width="90" height="5" fill="#5A5A57" opacity="0.4" />
      <rect x="290" y="138" width="60" height="5" fill="#000000" opacity="0.6" />
      <rect x="290" y="153" width="110" height="4" fill="#5A5A57" opacity="0.3" />
      <rect x="290" y="163" width="80" height="4" fill="#378ADD" opacity="0.5" />
      <rect x="290" y="173" width="100" height="4" fill="#378ADD" opacity="0.5" />
      <rect x="290" y="183" width="65" height="4" fill="#378ADD" opacity="0.5" />
      <rect x="290" y="193" width="60" height="5" fill="#000000" opacity="0.6" />
      <rect x="290" y="208" width="110" height="4" fill="#5A5A57" opacity="0.3" />
      <rect x="290" y="218" width="95" height="4" fill="#5A5A57" opacity="0.3" />

      {/* Score badge */}
      <rect x="330" y="240" width="70" height="28" fill="#FFFFFF" stroke="#378ADD" strokeWidth="1" />
      <text x="365" y="259" textAnchor="middle" fill="#378ADD" fontSize="11" fontWeight="600">9/10 fit</text>
    </svg>
  );
}

function WorkflowStep({ number, icon: Icon, title, description, color }: {
  number: string;
  icon: React.ElementType;
  title: string;
  description: string;
  color: string;
}) {
  return (
    <div className="flex gap-5">
      <div className="shrink-0 flex flex-col items-center">
        <div className={`w-10 h-10 ${color} flex items-center justify-center shrink-0`}>
          <Icon size={18} />
        </div>
        <div className="w-px flex-1 bg-rule-soft mt-3" />
      </div>
      <div className="pb-8">
        <p className="text-xs font-bold text-ink-muted mb-1">Step {number}</p>
        <h3 className="font-bold text-ink mb-1">{title}</h3>
        <p className="text-sm text-ink-muted leading-relaxed">{description}</p>
      </div>
    </div>
  );
}

const features = [
  {
    icon: Wand2,
    title: "AI Resume Tailoring",
    description: "Paste a job URL or description — Claude rewrites your resume bullets to match the role, then generates a targeted cover letter. All in under a minute.",
    color: "bg-ink text-paper",
  },
  {
    icon: Briefcase,
    title: "Application Tracker",
    description: "Track every role from Saved to Offer in a clean table or drag-and-drop kanban board. Know exactly where you stand at a glance.",
    color: "bg-ink text-paper",
  },
  {
    icon: Search,
    title: "Search Brief",
    description: "See exactly what parameters the job search agent uses — target roles, core skills, location, seniority. Toggle signals on and off and watch the queries update live.",
    color: "bg-ink text-paper",
  },
  {
    icon: Globe,
    title: "Multi-Profile",
    description: "Add multiple profiles for different people. Upload a PDF or DOCX resume — Claude extracts the structured data automatically. Each profile has its own search brief and application tracker.",
    color: "bg-ink text-paper",
  },
  {
    icon: Zap,
    title: "Powered by Claude",
    description: "Every AI operation — resume tailoring, cover letter generation, search brief extraction, humanised writing — runs on Claude Sonnet with full prompt caching for speed and cost efficiency.",
    color: "bg-ink text-paper",
  },
  {
    icon: Shield,
    title: "Local & Private",
    description: "Your resume data lives in JSON files on your machine. No cloud database, no accounts, no tracking. The FastAPI backend runs locally and your files never leave your computer.",
    color: "bg-ink text-paper",
  },
];

export default function AboutPage() {
  return (
    <div className="space-y-20">

      {/* Hero */}
      <section className="grid grid-cols-2 gap-12 items-center pt-4">
        <div>
          <div className="inline-flex items-center gap-2 border-[1.5px] border-ink text-ink text-xs font-bold px-3 py-1.5 mb-6">
            <Zap size={12} />
            Powered by Claude AI
          </div>
          <h1 className="text-4xl font-bold text-ink leading-tight mb-4">
            Your resume,<br />tailored for every role.
          </h1>
          <p className="text-ink-muted text-lg leading-relaxed mb-8">
            Resume. is an AI-powered job search tool that tailors your resume to each job description,
            tracks your applications, and gives you full transparency into the search parameters used on your behalf.
          </p>
          <div className="flex gap-3">
            <Link
              href="/tailor"
              className="flex items-center gap-2 bg-ink hover:bg-ink/80 text-paper px-5 py-2.5 text-sm font-bold transition-colors"
            >
              <Wand2 size={15} />
              tailor a resume
            </Link>
            <Link
              href="/"
              className="flex items-center gap-2 border-[1.5px] border-ink text-ink hover:bg-ink hover:text-paper px-5 py-2.5 text-sm font-medium transition-colors"
            >
              Go to Dashboard
              <ArrowRight size={14} />
            </Link>
          </div>
        </div>

        <div className="border-t-[1.5px] border-ink pt-5  aspect-[3/2]">
          <HeroIllustration />
        </div>
      </section>

      {/* How it works */}
      <section>
        <div className="mb-10">
          <p className="text-xs font-bold text-ink mb-2">How it works</p>
          <h2 className="text-2xl font-bold text-ink">from resume to interview in three steps</h2>
        </div>

        <div className="grid grid-cols-2 gap-12">
          <div>
            <WorkflowStep
              number="01"
              icon={FileText}
              title="Create your profile"
              description="Upload your existing resume as a PDF or DOCX. Claude parses it into a structured JSON profile — name, summary, experience with all bullet points, skills, education, and certifications."
              color="bg-ink text-paper"
            />
            <WorkflowStep
              number="02"
              icon={Wand2}
              title="Tailor to each role"
              description="Paste a LinkedIn URL or job description. Claude rewrites your summary and reorders your experience bullets to emphasise the most relevant work. A cover letter is generated in the same pass."
              color="bg-ink text-paper"
            />
            <WorkflowStep
              number="03"
              icon={Briefcase}
              title="Track every application"
              description="Download the tailored PDF and add the role to your tracker. Move applications between Saved, Applied, Interview, Offer, and Rejected — in a table or drag-and-drop kanban board."
              color="bg-ink text-paper"
            />
          </div>

          <div className="border-t-[1.5px] border-ink pt-5 flex flex-col justify-center">
            <p className="text-xs font-bold text-ink-muted mb-6">What the AI sees</p>
            <div className="space-y-3">
              {[
                { label: "Your full resume", sub: "Extracted from PDF or DOCX", dot: "bg-blue" },
                { label: "Job description", sub: "From URL or pasted text", dot: "bg-ink" },
                { label: "Humanise rules", sub: "No AI-sounding filler phrases", dot: "bg-yellow" },
                { label: "Search brief signals", sub: "Your target roles, skills, location", dot: "bg-blue-400" },
              ].map(item => (
                <div key={item.label} className="flex items-center gap-3 p-3 bg-paper">
                  <span className={`w-2.5 h-2.5 ${item.dot} shrink-0`} />
                  <div>
                    <p className="text-sm font-medium text-ink">{item.label}</p>
                    <p className="text-xs text-ink-muted">{item.sub}</p>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-6 p-4 bg-ink ">
              <p className="text-blue text-xs font-mono leading-relaxed">
                → Tailored resume PDF<br />
                → Cover letter<br />
                → Application tracked
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Features grid */}
      <section>
        <div className="mb-10">
          <p className="text-xs font-bold text-ink mb-2">Features</p>
          <h2 className="text-2xl font-bold text-ink">everything you need for a focused job search</h2>
        </div>

        <div className="grid grid-cols-3 gap-4">
          {features.map(({ icon: Icon, title, description, color }) => (
            <div key={title} className="border-t-[1.5px] border-ink pt-5">
              <div className={`w-10 h-10 flex items-center justify-center mb-4 ${color}`}>
                <Icon size={18} />
              </div>
              <h3 className="font-bold text-ink mb-2">{title}</h3>
              <p className="text-sm text-ink-muted leading-relaxed">{description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Tech stack */}
      <section className="border-t-[1.5px] border-ink pt-5">
        <div className="grid grid-cols-2 gap-10 items-center">
          <div>
            <p className="text-xs font-bold text-ink mb-2">Built on</p>
            <h2 className="text-2xl font-bold text-ink mb-4">a modern, open stack</h2>
            <p className="text-ink-muted text-sm leading-relaxed mb-6">
              Resume. is a locally-hosted tool — no SaaS subscription, no data leaving your machine.
              The Python backend handles AI operations and PDF generation; the Next.js frontend gives you a fast, reactive UI.
            </p>
            <Link href="/search-brief" className="flex items-center gap-2 text-ink text-sm font-medium hover:underline">
              See Search Brief transparency
              <ArrowRight size={14} />
            </Link>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {[
              { name: "Claude AI", role: "Tailoring, parsing, search brief", badge: "Anthropic" },
              { name: "Next.js 14", role: "Frontend — App Router, TypeScript", badge: "Vercel" },
              { name: "FastAPI", role: "Python API — async, typed routes", badge: "Python" },
              { name: "Playwright", role: "Headless PDF generation", badge: "Microsoft" },
              { name: "Tailwind CSS", role: "Utility-first styling system", badge: "UI" },
              { name: "SQLite", role: "Local application tracker DB", badge: "stdlib" },
            ].map(item => (
              <div key={item.name} className="bg-paper p-4 border border-rule-soft">
                <div className="flex items-center justify-between mb-1">
                  <p className="text-sm font-bold text-ink">{item.name}</p>
                  <span className="text-xs text-ink-muted border border-ink px-1.5 py-0.5">
                    {item.badge}
                  </span>
                </div>
                <p className="text-xs text-ink-muted">{item.role}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="text-center pb-4">
        <h2 className="text-2xl font-bold text-ink mb-3">ready to tailor your first resume?</h2>
        <p className="text-ink-muted text-sm mb-8">Takes less than a minute. Paste a job URL and let Claude do the work.</p>
        <Link
          href="/tailor"
          className="inline-flex items-center gap-2 bg-ink hover:bg-ink/80 text-paper px-6 py-3 text-sm font-bold transition-colors"
        >
          <Wand2 size={15} />
          get started
        </Link>
      </section>

    </div>
  );
}
