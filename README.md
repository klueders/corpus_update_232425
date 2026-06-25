# BVerfG Corpus Update (2023–2025)

```
Kilian Lüders
Universität Regensburg
kilian.lueders@ur.de
```

A pipeline to build a structured XML corpus of decisions by the German Federal Constitutional Court (*Bundesverfassungsgericht*, BVerfG) from 2023 to 2025, along with a metadata CSV file.

The pipeline downloads decision pages from the BVerfG website, parses the HTML, extracts and annotates the text, and serialises each decision as an XML document.

## Continuation of Existing Dataset

This corpus extends the work of Luisa Wendel and Christoph Möllers (2023):

**Korpus der Entscheidungen des Bundesverfassungsgerichts**
[https://doi.org/10.5281/zenodo.10369204](https://doi.org/10.5281/zenodo.10369204)

**Metadaten zu Entscheidungen des Bundesverfassungsgerichts**
[https://doi.org/10.5281/zenodo.5520913](https://doi.org/10.5281/zenodo.5520913)

See also the monograph by Luisa Wendel: **Textkonventionen am Bundesverfassungsgericht auf der Spur**
[https://doi.org/10.1628/978-3-16-164822-9](https://doi.org/10.1628/978-3-16-164822-9)

## Funding

The corpus update was funded through a project of the German Research Foundation (DFG): **< Freiheit // Gleichheit >: Grundrechtsperspektiven im europäisierten Verfassungsrecht** by Prof. Dr. Alexander Tischbirek

- Funder: **Deutsche Forschungsgemeinschaft**
- Title: **< Freiheit // Gleichheit >: Grundrechtsperspektiven im europäisierten Verfassungsrecht – eine hermeneutisch-empirische Annäherung**
- Number: **535386075**
- Link: https://gepris.dfg.de/gepris/projekt/535386075

The original corpus was funded by the German Research Foundation (DFG) **Leibniz Prize** for Prof. Dr. Christoph Möllers, LLM and developed within the project LLCon.

## LLM Usage

Claude Code was used to assist with documenting and commenting the code.
ChatGPT was used as an aid during the development and programming process.
All LLM-generated contributions were carefully reviewed and validated by the author.


---
# Documentation

## Code Base and Adaptation

This project builds upon the original code developed by Luisa Wendel. However, substantial modifications were necessary due to a redesign of the BVerfG website layout.

As part of this update, the codebase was restructured and streamlined:

**Skripte zur Erstellung und Fortführung des Korpus der Entscheidungen des Bundesverfassungsgerichts**
[https://doi.org/10.5281/zenodo.10369225](https://doi.org/10.5281/zenodo.10369225)

Please see, in particular, the documentation in this repository. Although the code has changed, the present project adopts the document structure and XML schema from Wendel. There are only a few minor differences resulting from changes made to the document structure on the Court Website. These include, for example:

- Tables of contents are now part of `<gruende>` and are marked with `tbeg="NA"`.
- Decisions with reasoniong in the Tenor are now included within `<tenor>`.

## Output

| Path | Description |
|------|-------------|
| `data/5_xml/*.xml` | One XML file per decision (857 files) |
| `data/6_metadata/metadata_232425.csv` / `.xlsx` | Final metadata table (857 rows × 39 columns) |

### XML structure

```xml
<bverfgdokument>
  <entscheidung>
    <leitsaetze>...</leitsaetze>  <!-- guiding principles, if published -->
    <rubrum>...</rubrum>          <!-- parties, procedure type -->
    <tenor>...</tenor>            <!-- operative part -->
    <gruende>
      <!-- Decisions with Ebene-1 outline: -->
      <ebene1 nr="1" zeichen="A" tbeg="tb">
        <absatz absatzID="0" rn="1" tbeg="tb">...</absatz>
        ...
      </ebene1>
      <!-- Decisions without outline structure (flat): -->
      <absatz absatzID="0" rn="1" tbeg="tb">...</absatz>
    </gruende>
  </entscheidung>
  <abwmeinungen>    
    <!-- dissenting opinions, if any -->
    <absatz rn="...">...</absatz>
  </abwmeinungen>
</bverfgdokument>
```

Each `<absatz>` carries a `tbeg` attribute classifying the paragraph as either
`tb` (Tatbestand – statement of facts) or `eg` (Entscheidungsgründe – legal reasoning).

### Metadata columns (39)

`dateiname`, `aktenzeichen`, `inAS`, `fundstelle`, `band`, `ersteSeite`, `letzteSeite`,
`jahr`, `monat`, `tag`, `entscheidungsart`, `spruchkoerper`, `gruende`, `abwmeinungen`,
`bvr`, `bvl`, `bvq`, `bvc`, `bve`, `bvf`, `bvo`, `bva`, `bvb`, `bvd`, `bvg`, `bvh`,
`bvj`, `bvk`, `bvm`, `bvn`, `bvp`, `bvt`, `pbvs`, `pbvu`, `pbvv`, `vz`,
`namenRichter`, `anzahlRichter`, `manuellErgaenzt`

The `bvr`–`vz` columns are boolean flags derived from `aktenzeichen` indicating which
BVerfG proceeding type applies. `inAS` flags decisions published in the official
collection (BVerfGE).

---

## Pipeline

The pipeline runs in five sequential steps, each implemented as a Jupyter notebook.

### Step 1 – `1_clean_raw_list.ipynb`

Parses the HTML search-result pages stored in `data/1_list_raw/` (one file per page,
50 results each). Extracts the URL and label of every result, removes duplicates,
derives a document ID from the URL filename, and saves the result to
`data/2_list_clean/clean_list.csv`.

### Step 2 – `2_download_data.ipynb`

Reads the clean list and downloads the full HTML page for each decision to
`data/3_html_raw/`. Already-downloaded files are skipped, so the notebook can be
re-run safely after interruptions.

### Step 3 – `3_data_managment.ipynb`

Filters the downloaded files to decisions from 2023, 2024, and 2025 (858 files).
Copies them to `data/4_html_raw_232425/`, preferring the manually corrected version
from `data/3_html_handcoding/` when one exists for a given file.

### Step 4 – `4_create_xml.ipynb`

Processes all 857 HTML files. For each file it:
1. Extracts sidebar metadata (ECLI, citation, date, senate, BVerfGE reference, Entscheidungsart).
2. Parses the decision content, handling two HTML formats used by the BVerfG website
   (`div.c-decision` for newer pages, `div.entscheidung` for legacy pages).
3. Extracts judge names and count (`namenRichter`, `anzahlRichter`) and the Aktenzeichen.
4. Annotates each Gründe paragraph as Tatbestand (`tb`) or Entscheidungsgründe (`eg`)
   using a regex-based classifier.
5. Writes one XML file to `data/5_xml/` and collects the metadata row.

After all files are processed, boolean proceeding-type columns (`bvr`, `bvl`, …) are
added and the raw metadata is saved as `data/6_metadata/metadata_232425_raw.csv`.

### Step 5 – `5_export_metadata.ipynb`

Loads the raw metadata and a sparse manual-corrections file
(`data/6_metadata/metadata_232425_cor.csv`). Corrections overwrite the corresponding
cells. The final table is exported as both `metadata_232425.csv` and `metadata_232425.xlsx`.

---

## Repository layout

```
corpus-update/
├── 1_clean_raw_list.ipynb
├── 2_download_data.ipynb
├── 3_data_managment.ipynb
├── 4_create_xml.ipynb
├── 5_export_metadata.ipynb
├── helper.py               # shared functions (used by step 4)
├── regex_positiv.txt       # positive regex  for TB/EG classification
├── regex_negativ.txt       # negative (override) regex  for TB/EG class
├── pyproject.toml          # uv project file with pinned dependencies
├── uv.lock                 # uv lockfile
├── .python-version         # pinned Python version (3.12)
└── data/
    ├── 1_list_raw/         # search-result HTML pages (input)
    ├── 2_list_clean/       # clean_list.csv
    ├── 3_html_raw/         # downloaded decision HTML files
    ├── 3_html_handcoding/  # manually corrected HTML files
    ├── 4_html_raw_232425/  # consolidated working set (2023–2025)
    ├── 5_xml/              # output XML files
    └── 6_metadata/         # metadata files
        ├── metadata_232425_raw.csv   # raw output of step 4
        ├── metadata_232425_cor.csv   # manual corrections
        ├── metadata_232425.csv       # final metadata (CSV)
        └── metadata_232425.xlsx      # final metadata (Excel)
```

---

## Setup

The project uses [uv](https://docs.astral.sh/uv/) for environment and dependency management.

```bash
# create the virtual environment and install all dependencies
uv sync
```

Python 3.12 is pinned in `.python-version`; all exact package versions are locked in `uv.lock`.

## Dependencies

| Package | Purpose |
|---------|---------|
| `beautifulsoup4` | HTML parsing |
| `lxml` | XML serialisation (BeautifulSoup XML parser) |
| `pandas` | tabular data handling |
| `openpyxl` | Excel export in step 5 |
| `torch` | backend for the transformers model |
| `transformers` | sentence-boundary detection model (`rcds/distilbert-SBD-de-judgements`) |
| `jupyter` | notebook runtime |

The TB/EG annotation uses the Hugging Face model
[rcds/distilbert-SBD-de-judgements](https://huggingface.co/rcds/distilbert-SBD-de-judgements)
for sentence splitting.
---

## TB/EG annotation

Every paragraph in the *Gründe* section is labelled as either:

- **`tb`** (Tatbestand) – the statement of facts and procedural history
- **`eg`** (Entscheidungsgründe) – the legal reasoning

The classifier tests only the **first sentence** of each paragraph against two sets of
regex rules (`regex_positiv.txt`, `regex_negativ.txt`). Once a paragraph triggers the
positive rule (and is not overridden by the negative rule), all subsequent paragraphs in the same section are also labelled `eg`.

Two annotation strategies are applied depending on the document structure:

- **Flat decisions** (no Ebene-1 outline): annotation runs sequentially from the start
  of the Gründe.
- **Decisions with Ebene-1 outline** (lettered or numbered top-level sections):
  paragraphs in section 0 and 1 are always `tb`; the classifier is applied from
  section 2 onwards.

## Manual Corrections

Manual corrections were applied to some files. They are documented in the metadata (`manuellErgaenzt`).
The corresponding corrections can be found in `data/3_html_handcoding/` and `data/6_metadata/metadata_232425_cor.csv`.