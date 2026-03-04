#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

OUTPUT_PATH="${1:-docs/api-documentation.pdf}"
mkdir -p "$(dirname "${OUTPUT_PATH}")"

python - "${OUTPUT_PATH}" <<'PY'
from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path


# Normalize env so OpenAPI generation is stable and not influenced by host shell values.
os.environ["APP_NAME"] = "Student Affordability Intelligence API"
os.environ["APP_VERSION"] = "0.1.0"
os.environ["DEBUG"] = "false"
os.environ["API_PREFIX"] = "/api/v1"
os.environ["DATABASE_URL"] = "sqlite:///./student_affordability.db"
os.environ["API_KEY_ENABLED"] = "false"
os.environ["API_KEY_HEADER_NAME"] = "X-API-Key"
os.environ["API_KEY_SECRET"] = ""
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["RATE_LIMIT_REQUESTS"] = "100"
os.environ["RATE_LIMIT_WINDOW_SECONDS"] = "60"
os.environ["AFFORDABILITY_RENT_WEIGHT"] = "0.6"
os.environ["AFFORDABILITY_PINT_WEIGHT"] = "0.2"
os.environ["AFFORDABILITY_TAKEAWAY_WEIGHT"] = "0.2"
os.environ["AFFORDABILITY_RENT_FLOOR_GBP_WEEKLY"] = "80.0"
os.environ["AFFORDABILITY_RENT_CEILING_GBP_WEEKLY"] = "300.0"
os.environ["AFFORDABILITY_COST_FLOOR_GBP"] = "2.0"
os.environ["AFFORDABILITY_COST_CEILING_GBP"] = "20.0"
os.environ["AFFORDABILITY_PINT_FLOOR_GBP"] = "2.0"
os.environ["AFFORDABILITY_PINT_CEILING_GBP"] = "10.0"
os.environ["AFFORDABILITY_TAKEAWAY_FLOOR_GBP"] = "5.0"
os.environ["AFFORDABILITY_TAKEAWAY_CEILING_GBP"] = "25.0"

from app.main import create_app


def _schema_type(schema: dict | None) -> str:
    if not schema:
        return "unknown"
    if "$ref" in schema:
        return schema["$ref"].split("/")[-1]
    kind = schema.get("type")
    if kind == "array":
        inner = _schema_type(schema.get("items"))
        return f"array[{inner}]"
    fmt = schema.get("format")
    return f"{kind}:{fmt}" if fmt else str(kind or "unknown")


def _build_lines(schema: dict) -> list[str]:
    lines: list[str] = []
    title = schema.get("info", {}).get("title", "API Documentation")
    version = schema.get("info", {}).get("version", "unknown")
    description = schema.get("info", {}).get("description", "")
    paths = schema.get("paths", {})
    components = schema.get("components", {})
    security_schemes = components.get("securitySchemes", {})

    lines.append(f"{title} - OpenAPI Documentation")
    lines.append(f"Version: {version}")
    lines.append("Generated from FastAPI OpenAPI schema.")
    if description:
        lines.extend(textwrap.wrap(description.replace("\n", " "), width=98))
    lines.append("")

    lines.append("Security Schemes")
    if not security_schemes:
        lines.append("  - none")
    else:
        for name in sorted(security_schemes):
            scheme = security_schemes[name]
            scheme_type = scheme.get("type", "unknown")
            location = scheme.get("in", "n/a")
            header_name = scheme.get("name", "n/a")
            lines.append(f"  - {name}: type={scheme_type}, in={location}, name={header_name}")
    lines.append("")

    lines.append("Endpoints")
    lines.append(f"  Total paths: {len(paths)}")
    lines.append("")

    method_order = {"get": 1, "post": 2, "put": 3, "patch": 4, "delete": 5, "options": 6, "head": 7}
    for path in sorted(paths):
        lines.append(path)
        operations = paths[path]
        methods = sorted(operations.keys(), key=lambda m: method_order.get(m.lower(), 99))
        for method in methods:
            op = operations[method]
            summary = op.get("summary", "")
            lines.append(f"  {method.upper()} - {summary}".rstrip())

            tags = op.get("tags", [])
            if tags:
                lines.append(f"    tags: {', '.join(tags)}")

            security = op.get("security", [])
            if security:
                security_flat = ", ".join(sorted(next(iter(item.keys())) for item in security if item))
                lines.append(f"    security: {security_flat}")

            params = op.get("parameters", [])
            if params:
                lines.append("    parameters:")
                for param in sorted(params, key=lambda p: (p.get("in", ""), p.get("name", ""))):
                    name = param.get("name", "unknown")
                    location = param.get("in", "unknown")
                    required = bool(param.get("required", False))
                    ptype = _schema_type(param.get("schema"))
                    lines.append(
                        f"      - {name} ({location}) type={ptype} required={'yes' if required else 'no'}"
                    )

            request_body = op.get("requestBody")
            if request_body:
                lines.append("    requestBody:")
                content = request_body.get("content", {})
                for ctype in sorted(content):
                    body_schema = content[ctype].get("schema")
                    lines.append(f"      - {ctype}: {_schema_type(body_schema)}")

            responses = op.get("responses", {})
            if responses:
                lines.append("    responses:")
                for code in sorted(responses):
                    resp = responses[code]
                    desc = (resp.get("description", "") or "").replace("\n", " ").strip()
                    content = resp.get("content", {})
                    if content:
                        body_types = []
                        for ctype in sorted(content):
                            body_types.append(f"{ctype}={_schema_type(content[ctype].get('schema'))}")
                        lines.append(f"      - {code}: {desc} [{'; '.join(body_types)}]".rstrip())
                    else:
                        lines.append(f"      - {code}: {desc}".rstrip())

            lines.append("")

    return lines


def _escape_pdf_text(value: str) -> str:
    ascii_text = value.encode("latin-1", "replace").decode("latin-1")
    ascii_text = ascii_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return "".join(ch if ord(ch) >= 32 else " " for ch in ascii_text)


def _wrap_lines(lines: list[str], width: int = 98) -> list[str]:
    wrapped: list[str] = []
    for line in lines:
        if not line:
            wrapped.append("")
            continue
        segments = textwrap.wrap(line, width=width, break_long_words=True, break_on_hyphens=False)
        wrapped.extend(segments if segments else [""])
    return wrapped


def _render_pdf(lines: list[str], output_path: Path) -> None:
    page_width = 612
    page_height = 792
    left_margin = 50
    top_y = 750
    line_height = 14
    lines_per_page = 48

    wrapped = _wrap_lines(lines)
    pages: list[list[str]] = [
        wrapped[i : i + lines_per_page] for i in range(0, len(wrapped), lines_per_page)
    ] or [[]]

    objects: list[bytes] = []
    num_pages = len(pages)
    first_page_obj = 3
    font_obj = first_page_obj + (num_pages * 2)

    # 1: catalog
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")

    # 2: pages tree
    kids = " ".join(f"{first_page_obj + i * 2} 0 R" for i in range(num_pages))
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {num_pages} >>".encode("ascii"))

    # page + content objects
    for i, page_lines in enumerate(pages):
        page_obj = first_page_obj + i * 2
        content_obj = page_obj + 1

        stream_lines = [
            "BT",
            "/F1 10 Tf",
            f"{line_height} TL",
            f"{left_margin} {top_y} Td",
        ]
        for idx, line in enumerate(page_lines):
            if idx > 0:
                stream_lines.append("T*")
            stream_lines.append(f"({_escape_pdf_text(line)}) Tj")
        stream_lines.append("ET")
        stream = ("\n".join(stream_lines) + "\n").encode("latin-1")

        page_dict = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] "
            f"/Resources << /Font << /F1 {font_obj} 0 R >> >> /Contents {content_obj} 0 R >>"
        )
        objects.append(page_dict.encode("ascii"))
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"endstream")

    # font object
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    pdf = bytearray()
    pdf.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{idx} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        if not obj.endswith(b"\n"):
            pdf.extend(b"\n")
        pdf.extend(b"endobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    pdf.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode("ascii"))
    pdf.extend(f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii"))

    output_path.write_bytes(bytes(pdf))


def main() -> None:
    output_path = Path(sys.argv[1]).expanduser().resolve()
    app = create_app()
    schema = app.openapi()
    lines = _build_lines(schema)
    _render_pdf(lines, output_path)
    print(f"Exported API documentation PDF: {output_path}")


if __name__ == "__main__":
    main()
PY
