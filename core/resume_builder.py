#!/usr/bin/env python3

import json
import argparse
from pathlib import Path
from datetime import datetime
from jinja2 import Environment

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


def load_json(path: str) -> dict:
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def render_html(data: dict, template_path: str) -> str:
    template_str = Path(template_path).read_text(encoding='utf-8')
    env = Environment(autoescape=False)
    return env.from_string(template_str).render(**data)


def write_html(html: str, path: str) -> None:
    Path(path).write_text(html, encoding='utf-8')
    print(f"✅ HTML: {path}")


def write_pdf(html: str, path: str, data: dict = None) -> None:
    if not PLAYWRIGHT_AVAILABLE:
        print("❌ Playwright not installed. Run: pip install playwright && playwright install chromium")
        return

    import tempfile, os
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as tmp:
        tmp.write(html)
        tmp_path = tmp.name

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox", "--disable-setuid-sandbox"])
            page = browser.new_page()
            page.goto(f'file://{tmp_path}')
            page.pdf(
                path=path,
                format='A4',
                print_background=True,
                margin={'top': '0', 'right': '0', 'bottom': '0', 'left': '0'},
            )
            browser.close()
        print(f"✅ PDF:  {path}")
    except Exception as e:
        print(f"❌ PDF error: {e}")
    finally:
        os.unlink(tmp_path)


def render_resume(data: dict, html_path: str, pdf_path: str) -> None:
    """Render resume data dict to HTML and PDF using the bundled template."""
    template_path = str(Path(__file__).parent / "resume_template.html")
    html = render_html(data, template_path)
    write_html(html, html_path)
    write_pdf(html, pdf_path)


def resolve_output_path(args, data: dict) -> str:
    if args.auto_name:
        output_dir = Path(__file__).parent.parent / "output"
        output_dir.mkdir(exist_ok=True)
        name_slug = data.get("name", "resume").lower().replace(" ", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        return str(output_dir / f"{name_slug}_resume_{timestamp}.html")
    return args.output


def main():
    parser = argparse.ArgumentParser(description='Generate a resume from JSON + Jinja2 template')
    parser.add_argument('--data',      default='resume_data.json',   help='JSON data file')
    parser.add_argument('--template',  default='resume_template.html', help='Jinja2 HTML template')
    parser.add_argument('--output',    default='resume_generated.html', help='Output HTML path')
    parser.add_argument('--auto-name', action='store_true', help='Auto-name output with name + timestamp')
    parser.add_argument('--pdf',       action='store_true', help='Also generate PDF via Playwright')
    args = parser.parse_args()

    if not Path(args.data).exists():
        print(f"❌ Data file not found: {args.data}")
        return
    if not Path(args.template).exists():
        print(f"❌ Template not found: {args.template}")
        return

    try:
        data = load_json(args.data)
        html_path = resolve_output_path(args, data)
        html = render_html(data, args.template)
        write_html(html, html_path)

        if args.pdf:
            pdf_path = html_path.replace('.html', '.pdf')
            write_pdf(html, pdf_path, data=data)

    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == '__main__':
    main()
