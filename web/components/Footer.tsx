import Link from "next/link";

const sitemap = [
  {
    heading: "Product",
    links: [
      { label: "Dashboard",    href: "/" },
      { label: "Tailor Resume", href: "/tailor" },
      { label: "Applications",  href: "/applications" },
      { label: "Search Brief",  href: "/search-brief" },
    ],
  },
  {
    heading: "Company",
    links: [
      { label: "About",   href: "/about" },
    ],
  },
  {
    heading: "Stack",
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
    <footer className="border-t border-warm-border bg-white mt-auto">
      <div className="max-w-5xl mx-auto px-6 py-12">
        <div className="grid grid-cols-4 gap-8">

          {/* Brand column */}
          <div className="col-span-1">
            <Link href="/" className="font-brand font-bold text-xl text-navy tracking-tight">
              NextRole<span className="text-accent">.</span>
            </Link>
            <p className="text-sm text-muted mt-3 leading-relaxed">
              AI-powered job search.<br />
              Tailor, track, and find the right roles — faster.
            </p>
            <p className="text-xs text-muted/60 mt-6">
              Built with{" "}
              <a href="https://anthropic.com" className="hover:text-accent transition-colors">
                Claude
              </a>
              {" "}by Anthropic.
            </p>
          </div>

          {/* Sitemap columns */}
          {sitemap.map(col => (
            <div key={col.heading}>
              <h4 className="text-xs font-semibold text-navy uppercase tracking-widest mb-4">
                {col.heading}
              </h4>
              <ul className="space-y-2.5">
                {col.links.map(link => (
                  <li key={link.label}>
                    <Link
                      href={link.href}
                      className="text-sm text-muted hover:text-navy transition-colors"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="border-t border-warm-border mt-10 pt-6 flex items-center justify-between">
          <p className="text-xs text-muted/60">
            © {new Date().getFullYear()} Resume. All rights reserved.
          </p>
          <p className="text-xs text-muted/60">
            Your data stays local — no cloud, no tracking.
          </p>
        </div>
      </div>
    </footer>
  );
}
