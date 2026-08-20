# Viwanda Mining

Use `viwanda_mining.ipynb` to collect Viwanda wholesale price PDF links, stream each PDF in memory, and extract price tables into JSON and CSV. It does not save PDF files.

Open `viwanda_mining.ipynb`, choose the `Python (fyp2026_backend venv)` kernel, and run the cells.

Outputs are written under:

```text
notebooks/mining/data/
```

Extraction requires `pdfplumber`.
