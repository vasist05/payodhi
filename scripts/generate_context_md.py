import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".vite",
    "dist",
    "build",
    ".gemini",
    ".system_generated",
    "checkpoints",
}

EXCLUDE_FILES = {
    "tree.txt",
    "sih-final-backend.zip",
    "package-lock.json",
    "context.md",
}

BINARY_EXTENSIONS = {
    ".pth", ".joblib", ".zip", ".png", ".jpg", ".jpeg", 
    ".nc", ".tif", ".tiff", ".pdf", ".ico", ".exe", ".dll",
    ".pyc", ".db", ".sqlite", ".parquet", ".pkl"
}

EXTENSION_TO_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".jsx": "jsx",
    ".html": "html",
    ".css": "css",
    ".json": "json",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".sql": "sql",
    ".sh": "bash",
    ".md": "markdown",
    ".txt": "text",
    ".ini": "ini",
    ".env": "bash",
    ".dockerfile": "dockerfile",
    "dockerfile": "dockerfile",
}

def should_include_file(file_path: Path) -> bool:
    rel_parts = file_path.relative_to(ROOT_DIR).parts
    for part in rel_parts[:-1]:
        if part in EXCLUDE_DIRS or part.startswith("."):
            return False
    if file_path.name in EXCLUDE_FILES:
        return False
    if file_path.suffix.lower() in BINARY_EXTENSIONS:
        return False
    return True

def generate_context_file(output_filename: str):
    output_path = ROOT_DIR / output_filename
    collected_files = []

    for root, dirs, files in os.walk(ROOT_DIR):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for file in sorted(files):
            file_path = Path(root) / file
            if should_include_file(file_path):
                collected_files.append(file_path)

    collected_files.sort(key=lambda p: str(p.relative_to(ROOT_DIR)).lower())

    with open(output_path, "w", encoding="utf-8") as out:
        out.write("# Payodhi — Complete Repository Code & Context (`context.md`)\n\n")
        out.write(f"**Total Source Files Included:** {len(collected_files)}\n\n")
        out.write("---\n\n")
        out.write("## Table of Contents\n\n")

        for idx, file_path in enumerate(collected_files, 1):
            rel_path = file_path.relative_to(ROOT_DIR).as_posix()
            anchor = rel_path.lower().replace("/", "-").replace(".", "-").replace("_", "-")
            out.write(f"{idx}. [{rel_path}](#{anchor})\n")

        out.write("\n---\n\n")

        for idx, file_path in enumerate(collected_files, 1):
            rel_path = file_path.relative_to(ROOT_DIR).as_posix()
            anchor = rel_path.lower().replace("/", "-").replace(".", "-").replace("_", "-")
            
            ext = file_path.suffix.lower()
            lang = EXTENSION_TO_LANG.get(ext, "")
            if file_path.name.lower() == "dockerfile":
                lang = "dockerfile"
            elif file_path.name.lower().startswith(".env"):
                lang = "bash"

            out.write(f"## {idx}. `{rel_path}`\n\n")
            out.write(f"<a id=\"{anchor}\"></a>\n\n")
            out.write(f"**Path:** `{rel_path}`  \n")
            out.write(f"**Size:** {file_path.stat().st_size} bytes  \n\n")

            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                out.write(f"```{lang}\n")
                out.write(content)
                if not content.endswith("\n"):
                    out.write("\n")
                out.write("```\n\n")
                out.write("---\n\n")
            except Exception as e:
                out.write(f"> Error reading file: {e}\n\n---\n\n")

    print(f"Successfully generated {output_path} with {len(collected_files)} files ({output_path.stat().st_size} bytes).")

if __name__ == "__main__":
    generate_context_file("context.md")
