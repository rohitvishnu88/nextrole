import Link from "next/link";

const sitemap = [
  {
    heading: "product",
    links: [
      { label: "dashboard",    href: "/" },
      { label: "tailor resume", href: "/tailor" },
      { label: "jobs",          href: "/jobs" },
      { label: "applications",  href: "/applications" },
      { label: "search brief",  href: "/search-brief" },
    ],
  },
  {
    heading: "company",
    links: [
      { label: "about",   href: "/about" },
    ],
  },
  {
    heading: "stack",
    links: [
      { label: "Claude AI",   href: "https://anthropic.com" },
      { label: "Next.js",     href: "https://nextjs.org" },
      { label: "FastAPI",     href: "https://fastapi.tiangolo.com" },
      { label: "Playwright",  href: "https://playwright.dev" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="border-t-[1.5px] border-ink bg-paper mt-auto">
      <div className="max-w-5xl mx-auto px-6 py-12">
        <div className="grid grid-cols-4 gap-8">

          {/* Brand column */}
          <div className="col-span-1">
            <Link href="/" className="font-bold text-xl text-ink">
              nextrole.
            </Link>
            <p className="text-sm text-ink-muted mt-3 leading-relaxed">
              AI-powered job search.<br />
              Tailor, track, and find the right roles — faster.
            </p>
            <p className="text-xs text-ink-muted mt-6">
              Built with{" "}
              <a href="https://anthropic.com" className="hover:text-ink transition-colors">
                claude
              </a>
              {" "}by Anthropic.
            </p>
          </div>

          {/* Sitemap columns */}
          {sitemap.map(col => (
            <div key={col.heading}>
              <h4 className="text-xs font-bold text-ink mb-4">
                {col.heading}
              </h4>
              <ul className="space-y-2.5">
                {col.links.map(link => (
                  <li key={link.label}>
                    <Link
                      href={link.href}
                      className="text-sm text-ink-muted hover:text-ink transition-colors"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="border-t-[1.5px] border-ink mt-10 pt-6 flex items-center justify-between">
          <p className="text-xs text-ink-muted">
            © {new Date().getFullYear()} Resume. All rights reserved.
          </p>
          <p className="text-xs text-ink-muted">
            Your data stays local — no cloud, no tracking.
          </p>
        </div>
      </div>
    </footer>
  );
}
