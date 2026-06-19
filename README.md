# Awesome Paperlist Maintainer

An automated maintenance tool for curated academic awesome paper lists on Github. Simply maintain a plain text file containing paper URLs. The system will automatically handle formatting, sectioning, ordering, etc.

### Setup
Run `pip install -e .` first.

### Add new papers
Add paper entry in `data/<project>/urls/` for the active dataset, following the format introduced in `data/testcase/urls/README.md`. For project-specific runs, set `PROJECT_NAME` and use the matching URL list and `textual_framework/beginning_<project>.md` files when they exist. Generated JSON metadata now lives under `data/<project>/meta_info/`, and unused legacy JSON files should be moved into `data/<project>/archived/`.

### Generate paper list
Run `python scripts/run.py` or `PYTHONPATH=. python scripts/run.py`. The default output Markdown page will be at `outputs/main.md`. Set `PROJECT_NAME=diversity` to generate the diversity project from its project-specific data and framework files. Each paper entry would show its title, paper link, time, authors, venue (if applicable), and keywords (optional).

For example,

> * **SWE-bench: Can Language Models Resolve Real-World GitHub Issues?** [[paper](http://arxiv.org/abs/2310.06770)] 2023-10  
 Carlos E. Jimenez, John Yang, Alexander Wettig, Shunyu Yao, Kexin Pei, Ofir Press, Karthik Narasimhan. ICLR 2024.
 Keywords: Code, Benchmark

Papers will be organized into sections and follow the time order (newest first). 
