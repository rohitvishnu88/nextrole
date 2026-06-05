import Link from "next/link";
import { FileText, Briefcase, Search, Wand2, ArrowRight, Zap, Shield, Globe } from "lucide-react";

function HeroIllustration() {
  return (
    <svg viewBox="0 0 480 320" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
      {/* Background blobs */}
      <circle cx="380" cy="60" r="120" fill="#FEF3E8" opacity="0.6" />
      <circle cx="100" cy="260" r="90" fill="#E8F5EE" opacity="0.5" />

      {/* Resume document */}
      <rect x="60" y="60" width="150" height="200" rx="12" fill="white" stroke="#E8E3D9" strokeWidth="1.5" />
      <rect x="80" y="90" width="80" height="8" rx="4" fill="#1A1714" opacity="0.8" />
      <rect x="80" y="108" width="110" height="5" rx="2.5" fill="#6B655C" opacity="0.4" />
      <rect x="80" y="118" width="90" height="5" rx="2.5" fill="#6B655C" opacity="0.4" />
      <rect x="80" y="138" width="60" height="5" rx="2.5" fill="#E07A3C" opacity="0.6" />
      <rect x="80" y="153" width="110" height="4" rx="2" fill="#6B655C" opacity="0.3" />
      <rect x="80" y="163" width="100" height="4" rx="2" fill="#6B655C" opacity="0.3" />
      <rect x="80" y="173" width="85" height="4" rx="2" fill="#6B655C" opacity="0.3" />
      <rect x="80" y="193" width="60" height="5" rx="2.5" fill="#E07A3C" opacity="0.6" />
      <rect x="80" y="208" width="110" height="4" rx="2" fill="#6B655C" opacity="0.3" />
      <rect x="80" y="218" width="95" height="4" rx="2" fill="#6B655C" opacity="0.3" />

      {/* AI sparkle in middle */}
      <circle cx="240" cy="160" r="36" fill="#E07A3C" opacity="0.12" />
      <circle cx="240" cy="160" r="24" fill="#E07A3C" opacity="0.2" />
      <circle cx="240" cy="160" r="14" fill="#E07A3C" />
      {/* Lightning bolt */}
      <path d="M243 152l-5 10h4l-5 10 9-12h-5l6-8z" fill="white" />

      {/* Arrows */}
      <path d="M218 160h-8" stroke="#E07A3C" strokeWidth="2" strokeLinecap="round" />
      <path d="M208 156l-6 4 6 4" stroke="#E07A3C" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M262 160h8" stroke="#E07A3C" strokeWidth="2" strokeLinecap="round" />
      <path d="M272 156l6 4-6 4" stroke="#E07A3C" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />

      {/* Tailored resume document */}
      <rect x="270" y="60" width="150" height="200" rx="12" fill="white" stroke="#E8E3D9" strokeWidth="1.5" />
      {/* Green accent stripe */}
      <rect x="270" y="60" width="6" height="200" rx="3" fill="#E07A3C" opacity="0.8" />
      <rect x="290" y="90" width="80" height="8" rx="4" fill="#1A1714" opacity="0.8" />
      <rect x="290" y="108" width="110" height="5" rx="2.5" fill="#6B655C" opacity="0.4" />
      <rect x="290" y="118" width="90" height="5" rx="2.5" fill="#6B655C" opacity="0.4" />
      <rect x="290" y="138" width="60" height="5" rx="2.5" fill="#E07A3C" opacity="0.6" />
      <rect x="290" y="153" width="110" height="4" rx="2" fill="#6B655C" opacity="0.3" />
      <rect x="290" y="163" width="80" height="4" rx="2" fill="#2D7A4F" opacity="0.5" />
      <rect x="290" y="173" width="100" height="4" rx="2" fill="#2D7A4F" opacity="0.5" />
      <rect x="290" y="183" width="65" height="4" rx="2" fill="#2D7A4F" opacity="0.5" />
      <rect x="290" y="193" width="60" height="5" rx="2.5" fill="#E07A3C" opacity="0.6" />
      <rect x="290" y="208" width="110" height="4" rx="2" fill="#6B655C" opacity="0.3" />
      <rect x="290" y="218" width="95" height="4" rx="2" fill="#6B655C" opacity="0.3" />

      {/* Score badge */}
      <rect x="330" y="240" width="70" height="28" rx="14" fill="#E8F5EE" stroke="#2D7A4F" strokeWidth="1" />
      <text x="365" y="259" textAnchor="middle" fill="#2D7A4F" fontSize="11" fontWeight="600">9/10 fit</text>
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
        <div className={`w-10 h-10 rounded-full ${color} flex items-center justify-center shrink-0`}>
          <Icon size={18} />
        </div>
        <div className="w-px flex-1 bg-warm-border mt-3" />
      </div>
      <div className="pb-8">
        <p className="text-xs font-semibold text-muted uppercase tracking-widest mb-1">Step {number}</p>
        <h3 className="font-semibold text-navy mb-1">{title}</h3>
        <p className="text-sm text-muted leading-relaxed">{description}</p>
      </div>
    </div>
  );
}

const features = [
  {
    icon: Wand2,
    title: "AI Resume Tailoring",
    description: "Paste a job URL or description — Claude rewrites your resume bullets to match the role, then generates a targeted cover letter. All in under a minute.",
    color: "bg-accent-light text-accent",
  },
  {
    icon: Briefcase,
    title: "Application Tracker",
    description: "Track every role from Saved to Offer in a clean table or drag-and-drop kanban board. Know exactly where you stand at a glance.",
    color: "bg-green-soft text-green-text",
  },
  {
    icon: Search,
    title: "Search Brief",
    description: "See exactly what parameters the job search agent uses — target roles, core skills, location, seniority. Toggle signals on and off and watch the queries update live.",
    color: "bg-yellow-50 text-yellow-700",
  },
  {
    icon: Globe,
    title: "Multi-Profile",
    description: "Add multiple profiles for different people. Upload a PDF or DOCX resume — Claude extracts the structured data automatically. Each profile has its own search brief and application tracker.",
    color: "bg-purple-50 text-purple-700",
  },
  {
    icon: Zap,
    title: "Powered by Claude",
    description: "Every AI operation — resume tailoring, cover letter generation, search brief extraction, humanised writing — runs on Claude Sonnet with full prompt caching for speed and cost efficiency.",
    color: "bg-orange-50 text-orange-700",
  },
  {
    icon: Shield,
    title: "Local & Private",
    description: "Your resume data lives in JSON files on your machine. No cloud database, no accounts, no tracking. The FastAPI backend runs locally and your files never leave your computer.",
    color: "bg-blue-50 text-blue-700",
  },
];

export default function AboutPage() {
  return (
    <div className="space-y-20">

      {/* Hero */}
      <section className="grid grid-cols-2 gap-12 items-center pt-4">
        <div>
          <div className="inline-flex items-center gap-2 bg-accent-light text-accent text-xs font-semibold px-3 py-1.5 rounded-full mb-6">
            <Zap size={12} />
            Powered by Claude AI
          </div>
          <h1 className="text-4xl font-bold text-navy leading-tight mb-4">
            Your resume,<br />tailored for every role.
          </h1>
          <p className="text-muted text-lg leading-relaxed mb-8">
            Resume. is an AI-powered job search tool that tailors your resume to each job description,
            tracks your applications, and gives you full transparency into the search parameters used on your behalf.
          </p>
          <div className="flex gap-3">
            <Link
              href="/tailor"
              className="flex items-center gap-2 bg-accent hover:bg-accent-hover text-white rounded-xl px-5 py-2.5 text-sm font-semibold transition-colors"
            >
              <Wand2 size={15} />
              Tailor a Resume
            </Link>
            <Link
              href="/"
              className="flex items-center gap-2 border border-warm-border text-navy hover:bg-cream rounded-xl px-5 py-2.5 text-sm font-medium transition-colors"
            >
              Go to Dashboard
              <ArrowRight size={14} />
            </Link>
          </div>
        </div>

        <div className="bg-white rounded-3xl border border-warm-border p-6 shadow-sm aspect-[3/2]">
          <HeroIllustration />
        </div>
      </section>

      {/* How it works */}
      <section>
        <div className="mb-10">
          <p className="text-xs font-semibold text-accent uppercase tracking-widest mb-2">How it works</p>
          <h2 className="text-2xl font-bold text-navy">From resume to interview in three steps</h2>
        </div>

        <div className="grid grid-cols-2 gap-12">
          <div>
            <WorkflowStep
              number="01"
              icon={FileText}
              title="Create your profile"
              description="Upload your existing resume as a PDF or DOCX. Claude parses it into a structured JSON profile — name, summary, experience with all bullet points, skills, education, and certifications."
              color="bg-accent-light text-accent"
            />
            <WorkflowStep
              number="02"
              icon={Wand2}
              title="Tailor to each role"
              description="Paste a LinkedIn URL or job description. Claude rewrites your summary and reorders your experience bullets to emphasise the most relevant work. A cover letter is generated in the same pass."
              color="bg-green-soft text-green-text"
            />
            <WorkflowStep
              number="03"
              icon={Briefcase}
              title="Track every application"
              description="Download the tailored PDF and add the role to your tracker. Move applications between Saved, Applied, Interview, Offer, and Rejected — in a table or drag-and-drop kanban board."
              color="bg-yellow-50 text-yellow-700"
            />
          </div>

          <div className="bg-white rounded-3xl border border-warm-border p-8 flex flex-col justify-center">
            <p className="text-xs font-semibold text-muted uppercase tracking-widest mb-6">What the AI sees</p>
            <div className="space-y-3">
              {[
                { label: "Your full resume", sub: "Extracted from PDF or DOCX", dot: "bg-green-500" },
                { label: "Job description", sub: "From URL or pasted text", dot: "bg-accent" },
                { label: "Humanise rules", sub: "No AI-sounding filler phrases", dot: "bg-yellow-400" },
                { label: "Search brief signals", sub: "Your target roles, skills, location", dot: "bg-blue-400" },
              ].map(item => (
                <div key={item.label} className="flex items-center gap-3 p-3 rounded-xl bg-cream">
                  <span className={`w-2.5 h-2.5 rounded-full ${item.dot} shrink-0`} />
                  <div>
                    <p className="text-sm font-medium text-navy">{item.label}</p>
                    <p className="text-xs text-muted">{item.sub}</p>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-6 p-4 bg-navy rounded-xl">
              <p className="text-green-400 text-xs font-mono leading-relaxed">
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
          <p className="text-xs font-semibold text-accent uppercase tracking-widest mb-2">Features</p>
          <h2 className="text-2xl font-bold text-navy">Everything you need for a focused job search</h2>
        </div>

        <div className="grid grid-cols-3 gap-4">
          {features.map(({ icon: Icon, title, description, color }) => (
            <div key={title} className="bg-white rounded-2xl border border-warm-border p-6">
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center mb-4 ${color}`}>
                <Icon size={18} />
              </div>
              <h3 className="font-semibold text-navy mb-2">{title}</h3>
              <p className="text-sm text-muted leading-relaxed">{description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Tech stack */}
      <section className="bg-white rounded-3xl border border-warm-border p-10">
        <div className="grid grid-cols-2 gap-10 items-center">
          <div>
            <p className="text-xs font-semibold text-accent uppercase tracking-widest mb-2">Built on</p>
            <h2 className="text-2xl font-bold text-navy mb-4">A modern, open stack</h2>
            <p className="text-muted text-sm leading-relaxed mb-6">
              Resume. is a locally-hosted tool — no SaaS subscription, no data leaving your machine.
              The Python backend handles AI operations and PDF generation; the Next.js frontend gives you a fast, reactive UI.
            </p>
            <Link href="/search-brief" className="flex items-center gap-2 text-accent text-sm font-medium hover:underline">
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
              <div key={item.name} className="bg-cream rounded-xl p-4 border border-warm-border">
                <div className="flex items-center justify-between mb-1">
                  <p className="text-sm font-semibold text-navy">{item.name}</p>
                  <span className="text-xs text-muted bg-white border border-warm-border px-1.5 py-0.5 rounded-full">
                    {item.badge}
                  </span>
                </div>
                <p className="text-xs text-muted">{item.role}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="text-center pb-4">
        <h2 className="text-2xl font-bold text-navy mb-3">Ready to tailor your first resume?</h2>
        <p className="text-muted text-sm mb-8">Takes less than a minute. Paste a job URL and let Claude do the work.</p>
        <Link
          href="/tailor"
          className="inline-flex items-center gap-2 bg-accent hover:bg-accent-hover text-white rounded-xl px-6 py-3 text-sm font-semibold transition-colors"
        >
          <Wand2 size={15} />
          Get started
        </Link>
      </section>

    </div>
  );
}
