import importlib
import json
import os
import time
from pathlib import Path

from src.paper import Paper

PROJECT_NAME = os.getenv("PROJECT_NAME", "example")

# Load project-specific config, falling back to default
def _load_config():
    for mod_name in (f"config.config_{PROJECT_NAME}", "config.config"):
        try:
            return importlib.import_module(mod_name)
        except ImportError:
            continue
    raise ImportError("No config module found")

_cfg = _load_config()
CUSTOM_CATEGORY_ORDER = _cfg.CUSTOM_CATEGORY_ORDER

project_data_root = Path("data") / PROJECT_NAME / "meta_info"
rawlist_file = project_data_root / "raw_paper_list.json"
paperlist_brief_file = project_data_root / "paper_list_brief.json"


def resolve_url_list_file(project_name: str | None = None) -> Path:
    project_name = project_name or os.getenv("PROJECT_NAME", "example")
    project_url_root = Path("data") / project_name / "urls"
    candidates = [
        project_url_root / "url_list.txt",
        project_url_root / f"url_list_{project_name}.txt",
        project_url_root / f"url_{project_name}.txt",
        project_url_root / "url_creativity.txt",
        project_url_root / "url_list_diversity.txt",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


url_list_file = resolve_url_list_file(PROJECT_NAME)

md_beginning_file = Path(f"textual_framework/beginning_{PROJECT_NAME}.md")
if not md_beginning_file.exists():
    md_beginning_file = Path("textual_framework/beginning.md")

md_ending_file = Path(f"textual_framework/ending_{PROJECT_NAME}.md")
if not md_ending_file.exists():
    md_ending_file = Path("textual_framework/ending.md")
    if not md_ending_file.exists():
        md_ending_file = None

md_brief_file = Path("outputs") / (f"{PROJECT_NAME}.md" if PROJECT_NAME != "example" else "main.md")


def url2rawlist(url_file_dir, rawlist_file_dir):
    """
    Merge URL list into raw paper list incrementally (never overwrites existing entries).
    """
    def load_url_list(url_file_dir):
        with open(url_file_dir, 'r') as file:
            return [line.strip() for line in file if line.strip()]

    def save_rawlist(rawlist, file_path):
        try:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w') as file:
                json.dump(rawlist, file, indent=4)
            print(f"Raw list saved to {file_path}.")
        except IOError as e:
            print(f"Error saving raw list to {file_path}: {e}")

    # Load existing raw entries keyed by link
    existing = {}
    if Path(rawlist_file_dir).exists():
        try:
            for item in json.loads(Path(rawlist_file_dir).read_text()):
                existing[item['link']] = item
        except Exception:
            pass

    url_list = load_url_list(url_file_dir)
    added = 0
    for url_line in url_list:
        parts = url_line.split(", ")
        url = parts[0].replace("https", "http")
        topic = parts[1] if len(parts) > 1 else "Other"
        keywords = [k.strip() for k in parts[2].split("/")] if len(parts) > 2 else []

        if url not in existing:
            existing[url] = {"title": "", "link": url, "topic": topic, "keywords": keywords}
            added += 1
        else:
            # Update topic/keywords on existing stubs that have none
            cur = existing[url]
            if (not cur.get("topic") or cur["topic"] == "Other") and topic != "Other":
                cur["topic"] = topic
            if not cur.get("keywords") and keywords:
                cur["keywords"] = keywords

    merged = list(existing.values())
    save_rawlist(merged, rawlist_file_dir)
    print(f"Raw list: {len(merged)} total ({added} new from URL list, {len(merged) - added} existing).")
    return merged


def generate_brief_paper_list(rawlist_file_dir, output_file_dir):
    """
    Fetch arXiv metadata for papers not yet in brief list (incremental).
    """
    def save_brief_paper_list(brief_list, file_path):
        try:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w') as file:
                json.dump(brief_list, file, indent=4)
            print(f"Brief paper list saved to {file_path}.")
        except IOError as e:
            print(f"Error saving brief paper list to {file_path}: {e}")

    rawlist = json.loads(Path(rawlist_file_dir).read_text())

    # Load existing brief keyed by link
    existing_brief = {}
    if Path(output_file_dir).exists():
        try:
            for item in json.loads(Path(output_file_dir).read_text()):
                existing_brief[item['link']] = item
        except Exception:
            pass

    to_process = [p for p in rawlist if p['link'] not in existing_brief]
    # Papers with title+authors from Zotero don't need an arXiv fetch
    ready = [p for p in to_process if p.get('title') and p.get('authors')]
    need_fetch = [p for p in to_process if not (p.get('title') and p.get('authors'))]
    print(f"Raw: {len(rawlist)} | Already in brief: {len(existing_brief)} | "
          f"Using Zotero metadata: {len(ready)} | Fetching from arXiv: {len(need_fetch)}")

    new_papers = []

    # Use existing Zotero metadata directly
    for paper in ready:
        paper_obj = Paper(paper)
        new_papers.append(paper_obj.__dict__)

    # Fetch from arXiv only for papers with no existing metadata
    for paper in need_fetch:
        paper_obj = Paper(paper)
        try:
            success = paper_obj.get_info_arxiv()
        except ValueError as e:
            print(f"Skipping {paper.get('link')}: {e}")
            continue
        if success is False:
            continue
        new_papers.append(paper_obj.__dict__)
        time.sleep(3)  # respect arXiv API rate limit (3s per their policy)

    merged = list(existing_brief.values()) + new_papers

    # Deduplicate by link (keep last occurrence which has freshest data)
    seen = {}
    for p in merged:
        seen[p['link']] = p
    merged = list(seen.values())

    save_brief_paper_list(merged, output_file_dir)
    print(f"Brief list: {len(merged)} total ({len(new_papers)} newly fetched).")
    return merged


def generate_markdown(paperlist_file_dir, output_md_file_dir):
    """
    Generate a markdown file from a list of papers with 2-level hierarchy.
    """
    def load_paperlist(file_path):
        try:
            with open(file_path, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            print(f"File {file_path} not found.")
            return []
        except json.JSONDecodeError:
            print(f"Error decoding JSON from {file_path}.")
            return []

    def organize_papers_by_hierarchy(papers):
        hierarchy = {}
        seen_links = set()
        for paper in papers:
            # Deduplicate
            if paper.get('link') in seen_links:
                continue
            seen_links.add(paper.get('link'))

            topic = paper.get("topic", "")
            if "/" in topic:
                main_category, sub_category = topic.split("/", 1)
            else:
                main_category, sub_category = topic, "General"

            hierarchy.setdefault(main_category, {}).setdefault(sub_category, []).append(paper)
        return hierarchy

    papers = load_paperlist(paperlist_file_dir)
    print(f"Successfully parsed {len(papers)} papers.")
    hierarchy = organize_papers_by_hierarchy(papers)

    Path(output_md_file_dir).parent.mkdir(parents=True, exist_ok=True)
    with open(output_md_file_dir, 'w') as md_file:
        with open(md_beginning_file, 'r', encoding='utf-8') as f:
            md_file.write(f.read())

        def sort_main(cat):
            try:
                return CUSTOM_CATEGORY_ORDER.index(cat)
            except ValueError:
                return len(CUSTOM_CATEGORY_ORDER) + 1

        for main_category in sorted(hierarchy.keys(), key=sort_main):
            md_file.write(f"## {main_category}\n\n")

            def sort_sub(sub):
                return (sub == "General", sub)

            for sub_category in sorted(hierarchy[main_category].keys(), key=sort_sub):
                if sub_category != "General":
                    md_file.write(f"### {sub_category}\n\n")
                else:
                    md_file.write("\n\n")

                category_papers = sorted(
                    hierarchy[main_category][sub_category],
                    key=lambda x: x.get("time", ""),
                    reverse=True
                )
                for paper in category_papers:
                    try:
                        paper_obj = Paper(paper)
                    except ValueError as e:
                        print(f"Skipping paper: {e}")
                        continue
                    md_file.write(paper_obj.brief_str() + "\n\n")

        if md_ending_file:
            with open(md_ending_file, 'r', encoding='utf-8') as f:
                md_file.write("\n" + f.read())


def main():
    url2rawlist(url_file_dir=url_list_file, rawlist_file_dir=rawlist_file)
    brief_paperlist = generate_brief_paper_list(rawlist_file_dir=rawlist_file, output_file_dir=paperlist_brief_file)
    if brief_paperlist:
        generate_markdown(paperlist_file_dir=paperlist_brief_file, output_md_file_dir=md_brief_file)
        print(f"Markdown file generated: {md_brief_file}")


if __name__ == "__main__":
    main()
