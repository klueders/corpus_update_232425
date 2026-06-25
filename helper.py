"""
helper.py – Shared utilities for 4_create_xml.ipynb.

  - Metadata extraction    – parse sidebar widgets and structured metadata fields
  - HTML cleaning          – normalise whitespace in extracted text
  - Heading detection      – identify and track Gründe outline levels (Ebene 1)
  - Content extraction     – walk the two HTML formats and build the content list
  - TB/EG annotation       – label Gründe paragraphs as Tatbestand or Entscheidungsgründe
  - XML output             – serialise the content list to a BVerfG XML document

The two HTML formats handled throughout are:
  - 'entscheidung'  (div.entscheidung)  – legacy format, older decisions
  - 'decision'      (div.c-decision)    – newer format, recent decisions
"""

import re
import os
from bs4 import BeautifulSoup
from transformers import pipeline


# ──────────────────────────────────────────────────────────────────────────────
# 1. Metadata Extraction
# ──────────────────────────────────────────────────────────────────────────────

def get_aktenzeichen(content_output):
    """
    Extract all Aktenzeichen (case numbers) from the Rubrum text.

    Matches patterns like '1 BvR 1234/23' or '2 BvL 5/22'.
    Returns them joined by '; ', or empty string if none are found.
    """
    rubrum_content = [e['content'] for e in content_output if e['segment'] == "rubrum"]
    rubrum_sring = "\n".join(rubrum_content)
    muster = re.compile(r"(?P<az>(1|2)[\s]+(BvA|BvB|BvC|BvD|BvE|BvF|BvG|BvH|BvJ|BvK|BvL|BvM|BvN|BvO|BvP|BvQ|BvR|BvT|PBvS|PBvU|PBvV)[\s]+[0-9]{1,4}/[0-9]{1,2})")
    results = [match.group("az") for match in muster.finditer(rubrum_sring)]
    if len(results) > 0:
        return "; ".join(results)
    return ""

def get_metadata(metadata_raw):
    """
    Parse the raw metadata dict (keyed by widget headline) into structured fields.

    Expected keys in metadata_raw:
      - 'European Case Law Identifier (ECLI):'
      - 'Zitiervorschlag:'
      - 'Fundstelle in der amtlichen Sammlung:' (optional – only for AS decisions)

    Returns a dict with keys: fundstelle, band, ersteSeite, letzteSeite,
    jahr, monat, tag, bezeichnung, spruchkoerper, ecli, anzahlRn.
    All fields are set to "NA" if the required information is missing.
    """
    ecli_key = 'European Case Law Identifier (ECLI):'
    citation_key = 'Zitiervorschlag:'

    if ecli_key not in metadata_raw.keys() or citation_key not in metadata_raw.keys():
        # Missing essential metadata – return placeholder values
        return {
            'inAS': "NA",
            'fundstelle': "NA",
            'band': "NA",
            'ersteSeite': "NA",
            'letzteSeite': "NA",
            'jahr': "NA",
            'monat': "NA",
            'tag': "NA",
            'bezeichnung': "NA",
            'spruchkoerper': "NA",
            'entscheidungsart': "NA",
            'ecli': "NA",
            'anzahlRn': "NA"
        }

    ecli = metadata_raw[ecli_key]
    bezeichnung = metadata_raw[citation_key]

    # Spruchkörper: derive senate/chamber identifier
    spruchkoerper = ""
    kammer = re.compile(r"[0-9](?=\. Kammer)")
    if "Plenum" in bezeichnung:
        spruchkoerper = "Plenum"
    if "Beschwerdekammer" in bezeichnung:
        spruchkoerper = "Beschwerdekammer"
    if "Kammer" in bezeichnung:
        if " des Ersten Senats" in bezeichnung:
            spruchkoerper = "I-" + kammer.search(bezeichnung).group(0)
        if " des Zweiten Senats" in bezeichnung:
            spruchkoerper = "II-" + kammer.search(bezeichnung).group(0)
    else:
        if " des Ersten Senats" in bezeichnung:
            spruchkoerper = "I"
        if " des Zweiten Senats" in bezeichnung:
            spruchkoerper = "II"

    # Entscheidungsdatum: extract day, month name, and year
    datum = ""
    day = ""
    month = ""
    year = ""
    datum = re.compile(r"(?P<day>[0-9]{1,2})\. (?P<month>Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember) (?P<year>[0-9]{4})")
    monate = {"Januar": 1, "Februar": 2, "März": 3, "April": 4, "Mai": 5, "Juni": 6, "Juli": 7, "August": 8, "September": 9, "Oktober": 10, "November": 11, "Dezember": 12}
    ergebnisDatum = datum.search(bezeichnung)
    if ergebnisDatum:
        day = str(int(ergebnisDatum.group("day")))
        month = monate[ergebnisDatum.group("month")]
        year = ergebnisDatum.group("year")

    # Anzahl Randnummern: extract the total paragraph count
    anzahlrn = ""
    musterAnzahlrn = re.compile(r"Rn\. (\()?1-(?P<anzahlrn>[0-9]{1,4})")
    ergebnisAnzahlrn = musterAnzahlrn.search(bezeichnung)
    if ergebnisAnzahlrn:
        anzahlrn = ergebnisAnzahlrn.group("anzahlrn")

    # Entscheidungsart: "Urteil" or "Beschluss"
    if "Urteil" in bezeichnung:
        entscheidungsart = "Urteil"
    elif "Beschluss" in bezeichnung:
        entscheidungsart = "Beschluss"
    else:
        entscheidungsart = ""

    
    # Fundstelle: only present for decisions published in the official collection (BVerfGE)
    if 'Fundstelle in der amtlichen Sammlung:' in metadata_raw.keys():
        musterFundstelle = re.compile(r"BVerfGE (?P<band>[0-9]{1,3}), (?P<anfs>[0-9]{1,3})( )?-( )?(?P<ends>[0-9]{1,3})")
        ergebnisFundstelle = musterFundstelle.search(metadata_raw['Fundstelle in der amtlichen Sammlung:'])
        fundstelle = ergebnisFundstelle.group(0)
        fundstelle = re.sub(" - ", "-", fundstelle)
        band = ergebnisFundstelle.group("band")
        anfs = ergebnisFundstelle.group("anfs")
        ends = ergebnisFundstelle.group("ends")
        inAS = 1
    else:
        inAS = 0
        fundstelle = "NA"
        band = "NA"
        anfs = "NA"
        ends = "NA"

    return {
        'inAS': inAS,
        'fundstelle': fundstelle,
        'band': band,
        'ersteSeite': anfs,
        'letzteSeite': ends,
        'jahr': year,
        'monat': month,
        'tag': day,
        'bezeichnung': bezeichnung.replace("\n", " "),
        'entscheidungsart': entscheidungsart,
        'spruchkoerper': spruchkoerper,
        'ecli': ecli,
        'anzahlRn': anzahlrn
    }


def raw_metadata_widgets(widgets):
    """
    Convert a list of sidebar widget elements into a flat dict.

    Each widget has an h2 headline (used as key) and a content div (used as value).
    """
    return {w.find("h2", class_="l-widget__headline").get_text(strip=True): w.find("div", class_="l-widget__content").get_text(strip=True) for w in widgets}

def get_meta_content(output):
    """
    Summarise which logical sections are present in the content list.

    Returns a dict with binary flags (1/0) for: leitsaetze, rubrum, tenor, gruende.
    Used to populate the corresponding metadata columns.
    """
    keys = [e['segment'] for e in output]
    return {
        'leitsaetze': int("leitsaetze" in keys),
        'rubrum': int("rubrum" in keys),
        'tenor': int("tenor" in keys),
        'gruende': int("gruende" in keys)
    }

def add_proceeding_bools(meta):
    """
    Add one boolean column per BVerfG proceeding type to the metadata DataFrame.

    Each column (e.g. 'bvr', 'bvl', 'bvq') is True if the corresponding
    Verfahrenszeichen (e.g. 'BvR', 'BvL', 'BvQ') appears in the 'aktenzeichen'
    column of that row. Covers all standard BVerfG proceeding codes.

    Returns the DataFrame with the new columns appended.
    """
    patterns = {
        "bvr": "BvR",
        "bvl": "BvL",
        "bvq": "BvQ",
        "bvc": "BvC",
        "bve": "BvE",
        "bvf": "BvF",
        "bvo": "BvO",
        "bva": "BvA",
        "bvb": "BvB",
        "bvd": "BvD",
        "bvg": "BvG",
        "bvh": "BvH",
        "bvj": "BvJ",
        "bvk": "BvK",
        "bvm": "BvM",
        "bvn": "BvN",
        "bvp": "BvP",
        "bvt": "BvT",
        "pbvs": "PBvS",
        "pbvu": "PBvU",
        "pbvv": "PBvV",
        "vz": "VZ"
    }

    for col, pattern in patterns.items():
        meta[col] = meta["aktenzeichen"].str.contains(pattern, na=False)

    return meta



# ──────────────────────────────────────────────────────────────────────────────
# 2. HTML Cleaning
# ──────────────────────────────────────────────────────────────────────────────

def clean_string(string_soup):
    """
    Normalise whitespace in a text string extracted from HTML:
      - Collapse runs of spaces/newlines into a single newline
      - Replace non-breaking spaces (\\xa0) with regular spaces
      - Collapse multiple consecutive spaces into one
    """
    string_soup = re.sub(r'[ ]*\n[ \n]*', '\n', string_soup)
    string_soup = re.sub(r'\xa0', ' ', string_soup)
    return re.sub(r'  +', ' ', string_soup)


def clean_newline_judges(string_judges):
    """
    Normalise whitespace in a judge-name block and convert newlines to comma separators.

    Collapses multiple newlines into one, then replaces each newline with ', '
    so that the result is a flat comma-separated list of surnames.
    """
    string_judges = re.sub(r'\s?\n+', '\n', string_judges)
    return string_judges.replace("\n", ", ")


# ──────────────────────────────────────────────────────────────────────────────
# 3. Heading Detection (Ebene 1 outline tracking)
# ──────────────────────────────────────────────────────────────────────────────

# The three supported numbering schemes for Ebene-1 headings in the Gründe section
alphabet_ABC = ["A", "B", "C", "D", "E", "F", "G", "H"]
alphabet_III = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV"]
alphabet_123 = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15"]


def identify_ebene(heading_text):
    """
    Detect the numbering scheme of the *first* Ebene-1 heading encountered.

    Returns a tuple (scheme, label) where scheme is one of 'ABC', 'III', '123',
    or ('NA', 'NA') if the text does not start a recognised sequence.
    Only 'A', 'I', or '1' are accepted as valid first headings.
    """
    heading_text = heading_text.strip(".")
    if heading_text == "A":
        return "ABC", heading_text
    elif heading_text == "I":
        return "III", heading_text
    elif heading_text == "1":
        return "123", heading_text
    return "NA", "NA"


def check_heading(heading_text, e_type, e_zeichen, e_nr):
    """
    Check whether heading_text is the next expected label in the current scheme.

    Parameters:
      heading_text – the candidate heading string
      e_type       – active scheme ('ABC', 'III', or '123')
      e_zeichen    – last heading label
      e_nr         – index of the heading

    Returns (new_zeichen, new_nr, is_heading)
    """
    heading_text = heading_text.strip(".")
    if e_type == "ABC":
        if heading_text == alphabet_ABC[e_nr]:
            return heading_text, e_nr + 1, True
    if e_type == "III":
        if heading_text == alphabet_III[e_nr]:
            return heading_text, e_nr + 1, True
    if e_type == "123":
        if heading_text == alphabet_123[e_nr]:
            return heading_text, e_nr + 1, True
    return e_zeichen, e_nr, False



# Compiled regex patterns for detecting section boundaries within a decision
musterLeitsaetze = re.compile(r"Leitsätze|Leitsatz|L e i t s ä t z e|L e i t s a t z")
musterRubrum = re.compile(r"BUNDESVERFASSUNGSGERICHT|BUNDESVERFASSUNGSGEIRCHT|Im Namen des Volkes|\n( )*?Bundesverfassungsgericht")
musterTenor = re.compile(r"beschlossen:|Recht(\s)erkannt:")
musterGruende = re.compile(r"Gründe:|Gründe :|G\sr\sü\sn\sd\se(:|\s)|Grnde:|G\sr\sn\sd\se(:|\s)")
musterAbwM = re.compile(r"(\n|(\s)(\s)+)Abweichende(\s)+Meinung(\s)+de[rs](\s)+(Richter[s]?[in]?[nen]?|Vizepräsident[ei]n|Präsident[ei]n)")


# ──────────────────────────────────────────────────────────────────────────────
# 4. Content Extraction
# ──────────────────────────────────────────────────────────────────────────────

# --- Legacy HTML format (div.entscheidung) ---

def get_judges_entscheidung(entscheidung_soup):
    """
    Extract the signing judges from the legacy 'entscheidung' HTML format.

    Looks for a <table summary="Unterschriften der Richter">.
    Returns a tuple (name_string, count) where name_string is a comma-separated
    list of judge surnames and count is the number of judges.
    Returns ("NA", 0) if the table is not found.
    """
    content = entscheidung_soup.find("table", {"summary": "Unterschriften der Richter"})
    if not bool(content):
        return "NA"
    name_judges = clean_newline_judges(content.text.strip())
    count_judges = len(name_judges.split(", "))
    return name_judges, count_judges 


def get_content_entscheidung(entscheidung_div):
    """
    Extract structured content from the legacy 'entscheidung' HTML format.

    Iterates over div.absatz elements and assigns each to a segment
    (leitsaetze, rubrum, tenor, gruende, abwmeinungen) by matching regex patterns
    against the text. Ebene-1 headings within the Gründe are tracked to populate
    ebene1nr and ebene1zeichen fields. Consecutive absatzIDs are assigned to
    Gründe paragraphs.

    Returns:
      content_list      – list of paragraph dicts (excludes dissenting opinions)
      sondervota_output – list of paragraph dicts for dissenting opinions
    """
    output = list()
    segment = None

    ebene1type = "NA"
    ebene1nr = 0
    ebene1zeichen = "NA"

    for abs in entscheidung_div.find_all("div", attrs={'class': 'absatz'}):
        rn = abs.find("div", attrs={'class': 'rechts'}).text.strip()
        if rn == "":
            rn == "NA"
        content = abs.find("div", attrs={'class': 'links'}).text.strip()
        content = clean_string(content)

        # Determine the current segment based on section-boundary patterns
        if segment == None:
            ergebnisLeitsaetze = re.search(musterLeitsaetze, content)
            if bool(ergebnisLeitsaetze):
                segment = "leitsaetze"

        ergebnisRubrum = re.search(musterRubrum, content)
        if bool(ergebnisRubrum):
            segment = "rubrum"

        ergebnisGruende = re.search(musterGruende, content)
        if bool(ergebnisGruende):
            segment = "gruende"

        ergebnisabwM = re.search(musterAbwM, content)
        if bool(ergebnisabwM):
            segment = "abwmeinungen"

        # Redact attorney information (Bevollmächtigter block)
        if abs.find("div", attrs={'class': 'bvm3'}):
            content = "Bevollmächtigter: [BEVOLLM. ENTFERNT]"

        # Track Ebene-1 headings within the Gründe section
        is_heading = False
        if segment == "gruende":
            heading = abs.find('h5', attrs={'class': 'p--heading-4'})
            if bool(heading):
                if ebene1type == "NA":
                    ebene1type, ebene1zeichen = identify_ebene(heading.text.strip())
                    is_heading = True
                    ebene1nr += 1
                else:
                    ebene1zeichen, ebene1nr, is_heading = check_heading(heading.text.strip(), ebene1type, ebene1zeichen, ebene1nr)

        if content != "":
            if is_heading:
                output.append({
                    'segment': segment,
                    'subsegment': "heading",
                    'rn': "NA",
                    'content': content,
                    'ebene1nr': ebene1nr,
                    'ebene1zeichen': ebene1zeichen
                })
            elif segment == "gruende":
                output.append({
                        'segment': segment,
                        'subsegment': "content",
                        'rn': rn,
                        'content': content,
                        'ebene1nr': ebene1nr,
                        'ebene1zeichen': ebene1zeichen
                    })
            else:
                output.append({
                    'segment': segment,
                    'subsegment': "content",
                    'rn': rn,
                    'content': content,
                    'ebene1nr': "NA",
                    'ebene1zeichen': ebene1zeichen
                })

        # Tenor starts immediately after the closing formula of the Rubrum
        ergebnisTenor = re.search(musterTenor, content)
        if bool(ergebnisTenor) and segment == "rubrum":
            segment = "tenor"

    # Assign sequential absatzIDs to Gründe paragraphs and convert ebene1nr to string
    clean_output_id = list()
    absatzID = 0
    for i, e in enumerate(output):
        if e['segment'] == "gruende":
            e['absatzID'] = absatzID
            absatzID += 1
        else:
            e['absatzID'] = "NA"
        e['ebene1nr'] = str(e['ebene1nr'])
        clean_output_id.append(e)

    # Separate dissenting opinions from the main content list
    sondervota_output = [e for e in clean_output_id if e['segment'] == "abwmeinungen"]
    clean_output_id = [e for e in clean_output_id if e['segment'] != "abwmeinungen"]

    return clean_output_id, sondervota_output


# --- Newer HTML format (div.c-decision) ---

def get_judges_decision(decison_soup):
    """
    Extract the signing judges from the newer 'c-decision' HTML format.

    Looks for a <ul class="c-decision__judges">.
    Returns a tuple (name_string, count) where name_string is a comma-separated
    list of judge surnames and count is the number of judges.
    Returns ("NA", 0) if the list is not found.
    """
    content = decison_soup.find("ul", {"class": "c-decision__judges"})
    if not bool(content):
        return "NA"
    name_judges = clean_newline_judges(content.text.strip())
    count_judges = len(name_judges.split(", "))
    return name_judges, count_judges 


def get_gruende_decision(reasons, output):
    """
    Parse the Gründe section from the newer 'c-decision' HTML format and append
    paragraph dicts to output.

    Iterates over direct children of the reasons div. Paragraph types:
      - 'p.is-anchor'  – marginal number (Randnummer), stored as rn for next paragraph
      - 'p.justify'    – regular Gründe paragraph
      - 'p' (no class) – unnumbered paragraph (e.g. citation block)
      - 'h2' / 'h3'    – potential Ebene-1 headings; tracked via identify_ebene / check_heading
      - other tags     – treated as content (e.g. blockquotes)

    Paragraphs before the 'Gründe:' heading are tagged as subsegment='pregruende'.
    Raises ValueError if bare text is found outside any tag.

    Returns the updated output list.
    """
    absatzID = 0
    pre_gruende = True
    rn = "NA"
    ebene1type = "NA"
    ebene1nr = 0 # fängt immer bei 0 an
    ebene1zeichen = "NA"

    for child in reasons.children:
        is_heading = False
        if child.name == None:
            if child.strip() != "":
                raise ValueError("Content not in tags: " + child.strip())
        else:
            content = child.text
            content = clean_string(content)
            if bool(re.search(musterGruende, content)):
                # The 'Gründe:' heading itself marks the transition from pre-Gründe to Gründe
                pre_gruende = False
                output.append({'segment': "gruende", 'subsegment': "gruende", 'rn': rn, 'content': content, 'ebene1nr': ebene1nr, 'ebene1zeichen': ebene1zeichen})
            else:
                if pre_gruende:
                    output.append({'segment': "gruende", 'subsegment': "pregruende", 'rn': rn, 'content': content, 'ebene1nr': ebene1nr, 'ebene1zeichen': ebene1zeichen})
                else:
                    if child.name == "p" and child.get('class') == None:
                        # Unnumbered paragraph (e.g. legislative quote)
                        output.append({'segment': "gruende", 'subsegment': "content", 'rn': "NA", 'content': content, 'ebene1nr': ebene1nr, 'ebene1zeichen': ebene1zeichen})
                    elif child.name == "p" and child.get('class')[0] == "is-anchor":
                            # Marginal number – used as rn for the following paragraph
                            rn = child.text.strip()
                    elif child.name == "p" and child.get('class')[0] == "justify":
                            output.append({ 'segment': "gruende", 'subsegment': "content", 'rn': rn, 'content': content, 'ebene1nr': ebene1nr, 'ebene1zeichen': ebene1zeichen})
                    elif child.name == "h3" or child.name == "h2":
                        # Check if this is an Ebene-1 heading
                        if ebene1type == "NA":
                            # First heading encountered – determine the numbering scheme
                            ebene1type, ebene1zeichen = identify_ebene(child.text.strip())
                            if ebene1zeichen != "NA":
                                ebene1nr += 1
                                is_heading = True
                        else:
                            # Subsequent heading – verify it continues the sequence
                            ebene1zeichen, ebene1nr, is_heading = check_heading(child.text.strip(), ebene1type, ebene1zeichen, ebene1nr)
                        if is_heading:
                            output.append({ 'segment': "gruende", 'subsegment': "heading", 'rn': "NA", 'content': content, 'ebene1nr': ebene1nr, 'ebene1zeichen': ebene1zeichen})
                        else:
                            # Heading-like element that is not an Ebene-1 heading (e.g. sub-level)
                            output.append({'segment': "gruende", 'subsegment': "content", 'rn': "NA", 'content': content, 'ebene1nr': ebene1nr, 'ebene1zeichen': ebene1zeichen})
                    else:
                        # Other content (often block quotes or formatted law text)
                        output.append({'segment': "gruende", 'subsegment': "content", 'rn': "NA", 'content': content, 'ebene1nr': ebene1nr, 'ebene1zeichen': ebene1zeichen})
    return output


def get_content_decision(decison_soup):
    """
    Extract structured content from the newer 'c-decision' HTML format.

    Parses the following named sections if present:
      - div.c-decision__principles  -> leitsaetze
      - div.c-decision__rubrum      -> rubrum
      - div.c-decision__tenor       -> tenor
      - div.c-decision__reasons     -> gruende (via get_gruende_decision)
      - ul.c-decision__judges       -> appended to Gründe as subsegment='judges'
      - ul.c-decision__sondervota   -> dissenting opinions (returned separately)

    Special case: if a tenor is present but no Gründe, the judge list is appended
    to the Tenor text to keep the dataset uniform.

    Returns:
      content_list      – list of paragraph dicts (excludes dissenting opinions)
      sondervota_output – list of paragraph dicts for dissenting opinions
    """
    principles = decison_soup.find("div", {"class": "c-decision__principles"})
    rubrum = decison_soup.find("div", {"class": "c-decision__rubrum"})
    tenor = decison_soup.find("div", {"class": "c-decision__tenor"})
    judges = decison_soup.find("ul", {"class": "c-decision__judges"})
    reasons = decison_soup.find("div", {"class": "c-decision__reasons"})
    sondervota = decison_soup.find("ul", {"class": "c-decision__sondervota"})

    output = list()

    if bool(principles):
        content = principles.text.strip()
        content = clean_string(content)
        output.append({'segment': "leitsaetze", 'subsegment': "", 'rn': None, 'content': content, 'ebene1nr': "NA", 'ebene1zeichen': "NA"})

    if bool(rubrum):
        content = rubrum.text.strip()
        content = clean_string(content)
        # Redact attorney information from the Rubrum
        content = re.sub(r"Bevollmächtigter?:.*?gegen", "Bevollmächtigte: [BEVOLLM. ENTFERNT]\ngegen", content, flags=re.DOTALL)
        output.append({'segment': "rubrum", 'subsegment': "", 'rn': None, 'content': content, 'ebene1nr': "NA", 'ebene1zeichen': "NA"})

    if bool(tenor):
        if not bool(reasons) and bool(judges):
            # Special case: no Gründe section – append judge names to the Tenor
            content = tenor.text.strip()
            content = clean_string(content) + "\n" + judges.text.strip()
            output.append({'segment': "tenor", 'subsegment': "", 'rn': None, 'content': content, 'ebene1nr': "NA", 'ebene1zeichen': "NA"})
        else:
            content = tenor.text.strip()
            content = clean_string(content)
            output.append({'segment': "tenor", 'subsegment': "", 'rn': None, 'content': content, 'ebene1nr': "NA", 'ebene1zeichen': "NA"})

            if bool(reasons):
                output = get_gruende_decision(reasons, output)

            if bool(judges):
                # Append judge names as the last paragraph of the Gründe section
                ebene1nr = output[-1]['ebene1nr']
                ebene1zeichen = output[-1]['ebene1zeichen']
                output.append({'segment': "gruende", 'subsegment': "judges", 'rn': "NA", 'content': judges.text.strip(), 'ebene1nr': ebene1nr, 'ebene1zeichen': ebene1zeichen})
    else:
        raise ValueError("Kein Tenor!")

    # Merge consecutive paragraphs that share the same rn, segment, and subsegment
    clean_output = list()
    for entry in output:
        if clean_output and entry['rn'] == clean_output[-1]['rn'] and entry['segment'] == clean_output[-1]['segment']and entry['subsegment'] == clean_output[-1]['subsegment']:
            # Combine content with newline
            clean_output[-1]['content'] += " " + entry['content']
        else:
            # Add a copy of the current entry
            clean_output.append(entry)

    # Assign sequential absatzIDs to Gründe paragraphs and convert ebene1nr to string
    clean_output_id = list()
    absatzID = 0
    for i, e in enumerate(clean_output):
        if e['segment'] == "gruende":
            e['absatzID'] = absatzID
            absatzID += 1
        else:
            e['absatzID'] = "NA"
        e['ebene1nr'] = str(e['ebene1nr'])
        clean_output_id.append(e)

    # Parse dissenting opinions (Sondervota) into a separate list
    rn = "NA"
    sondervota_output = list()
    if sondervota != None:
        for sondervotum in sondervota.find_all("li", {"class": "c-decision__sondervotum"}):
            for child in sondervotum.children:
                if child.name == None:
                    if child.strip() != "":
                        raise ValueError("Content not in tags: " + child.strip())
                else:
                    content = child.text
                    content = clean_string(content)
                    if child.name == "p" and child.get('class')[0] == "is-anchor":
                        rn = child.text.strip()
                    elif child.name == "p" and child.get('class')[0] == "justify":
                        sondervota_output.append({'rn': rn, 'content': content})
                    else:
                        # Other content (often block quotes)
                        sondervota_output.append({'rn': "NA", 'content': content})
    return clean_output_id, sondervota_output


# ──────────────────────────────────────────────────────────────────────────────
# 5. TB/EG Annotation
# ──────────────────────────────────────────────────────────────────────────────

# Load regex rules for Tatbestand/Entscheidungsgründe classification
with open("regex_positiv.txt", "r") as fp:
    einlesen = re.sub("\n", "", fp.read())
pattern_regex_positive = re.compile(einlesen)

with open("regex_negativ.txt", "r") as fp:
    einlesen = re.sub("\n", "", fp.read())
pattern_regex_negative = re.compile(einlesen)


# Load the sentence boundary detection model for German legal texts
model_name = "rcds/distilbert-SBD-de-judgements"
pipe = pipeline("token-classification", model=model_name, tokenizer=model_name)


def split_sentences(rn_text: str):
    """
    Split a paragraph into sentences using the German legal SBD model.

    Uses token-level 'B-Sentence' tags to locate sentence boundaries.
    Returns a list of sentence strings.
    """
    tok_class = pipe(rn_text)
    breaks = [tok['start'] for tok in tok_class if tok['entity'] == "B-Sentence"]
    breaks.append(len(rn_text))
    sent_list = [rn_text[breaks[i]:breaks[i+1]].strip() for i in range(len(breaks)-1)]
    return sent_list


def check_rn_TB(rn_content) -> bool:
    """
    Determine whether a paragraph marks the start of the Tatbestand section.

    Only the first sentence of the paragraph is tested against the regex rules:
      - A positive match (pattern_regex_positive) sets result to True.
      - A subsequent negative match (pattern_regex_negative) overrides to False.

    Returns True if the paragraph is classified as Tatbestand-opening, else False.
    """
    sentences = split_sentences(rn_content)
    if len(sentences) > 1:
        sentence = sentences[0]
    else:
        sentence = rn_content

    result = False

    if not result:
        # result with positive ORS-rules
        if pattern_regex_positive.search(sentence) != None:
            result = True
            if pattern_regex_negative.search(sentence) != None:
                result = False
    return result


def get_TBEG_anno_flat(content_list):
    """
    Assign TB/EG labels to decisions without any Ebene-1 structure (flat Gründe).

    Iterates through paragraphs in order. The label starts as 'tb' (Tatbestand)
    and switches to 'eg' (Entscheidungsgründe) as soon as check_rn_TB returns True
    for a content paragraph. The switch is permanent (no revert to 'tb').
    Non-Gründe paragraphs receive tbeg='NA'.

    Returns the annotated content list.
    """
    tbeg = "tb"
    output = list()
    for abs in content_list:
        if abs['segment'] == "gruende":
            if abs['subsegment'] == "content":
                if check_rn_TB(abs['content']):
                    tbeg = "eg"
            abs['tbeg'] = tbeg
        else:
            abs['tbeg'] = "NA"
        output.append(abs)
    return output


def get_TBEG_anno_ebene(content_list, nr_set):
    """
    Assign TB/EG labels to decisions that have an Ebene-1 outline structure.

    Rules:
      - Paragraphs in ebene1nr 0 or 1 are always 'tb' (preamble / first section).
      - For ebene1nr >= 2, check_rn_TB is applied and the label switches to 'eg'
        once triggered (non-reversible within the section).
    After the initial pass, headings, the 'Gründe:' line, and the judge list receive
    their tbeg by looking at the surrounding paragraphs.

    Returns the annotated content list.
    """
    tbeg = "tb"
    output = list()
    for abs in content_list:
        if abs['segment'] == "gruende" and abs['subsegment'] == "content":
            if abs['ebene1nr'] in ["0","1"]:
                abs['tbeg'] = "tb"
            else:
                if check_rn_TB(abs['content']):
                    tbeg = "eg"
                abs['tbeg'] = tbeg
        else:
            abs['tbeg'] = "NA"
        output.append(abs)

    # Fill in tbeg for non-content Gründe entries (headings, 'Gründe:' line, judge list)
    for i, abs in enumerate(output):
        if abs['segment'] == "gruende":
            if abs['tbeg'] == "NA":
                tmp = "NA"
                if abs['subsegment'] == "gruende":
                    tmp = "tb"
                if abs['subsegment'] == "judges":
                    tmp = output[i-1]['tbeg']
                if abs['subsegment'] == "heading":
                    tmp = output[i+1]['tbeg']
                output[i]['tbeg'] = tmp

    return output


def get_tbeg(input):
    """
    Dispatch to the correct TB/EG annotation function based on the Ebene-1 structure.

    Checks the set of distinct ebene1nr values across all paragraphs:
      - {0}              – no outline structure  -> get_TBEG_anno_flat
      - {0, 1, 2, ...}   – Ebene-1 structure     -> get_TBEG_anno_ebene
      - {0, 1} only      – invalid state          -> raises ValueError
      - empty set        – no Gründe at all       -> returns input unchanged

    Returns the annotated content list.
    """
    ebene1nr_set = set([int(e["ebene1nr"]) for e in input if e["ebene1nr"] != "NA"])

    if ebene1nr_set == set([0, 1]):
        raise ValueError("Error Ebene1!")
    if ebene1nr_set == {0}:
        # No Ebene-1 outline – use flat annotation
        doc = get_TBEG_anno_flat(input)
        return doc
    if len(ebene1nr_set) > 2:
        # Ebene-1 outline present – use structured annotation
        doc = get_TBEG_anno_ebene(input, ebene1nr_set)
        return doc
    if len(ebene1nr_set) != 0:
        raise ValueError("Error Ebene1!")
    return input


# ──────────────────────────────────────────────────────────────────────────────
# 6. XML Output
# ──────────────────────────────────────────────────────────────────────────────

def save_xml(output, sondervota_output, path, file):
    """
    Serialise the annotated content list to a BVerfG XML document and write it to disk.

    XML structure:
      <bverfgdokument>
        <entscheidung>
          <leitsaetze>...</leitsaetze>          (if present)
          <rubrum>...</rubrum>                  (if present)
          <tenor>...</tenor>                    (if present)
          <gruende>
            <ebene1 nr="..." zeichen="..." tbeg="...">   (if Ebene-1 outline exists)
              <absatz absatzID="..." ebene1nr="..." ebene1zeichen="..." rn="..." tbeg="...">
                ...
              </absatz>
            </ebene1>
            -- OR --
            <absatz absatzID="..." rn="..." tbeg="...">  (flat structure, no Ebene-1)
              ...
            </absatz>
          </gruende>
        </entscheidung>
        <abwmeinungen>                          (if sondervota_output is non-empty)
          <absatz rn="...">...</absatz>
        </abwmeinungen>
      </bverfgdokument>

    The Gründe section uses <ebene1> wrapper tags when the last paragraph has a
    non-'NA' ebene1zeichen; otherwise paragraphs are written directly into <gruende>.

    Parameters:
      output           – annotated content list from get_tbeg()
      sondervota_output – list of dissenting-opinion paragraph dicts (may be empty)
      path             – output directory (must end with '/')
      file             – original HTML filename (e.g. 'rk20241205_1bvr240624.html')
    """
    new_soup = BeautifulSoup('<?xml version="1.0" encoding="utf-8"?><bverfgdokument></bverfgdokument>', 'xml')

    entscheidung = new_soup.new_tag('entscheidung')
    new_soup.bverfgdokument.append(entscheidung)

    leitsaetze_content = [e['content'] for e in output if e['segment'] == "leitsaetze"]
    if len(leitsaetze_content) > 0:
        leitsaetze_content = "\n".join(leitsaetze_content)
        leitsaetze = new_soup.new_tag('leitsaetze')
        leitsaetze.string = leitsaetze_content
        new_soup.bverfgdokument.entscheidung.append(leitsaetze)

    rubrum_content = [e['content'] for e in output if e['segment'] == "rubrum"]
    if len(rubrum_content) > 0:
        rubrum_content = "\n".join(rubrum_content)
        rubrum = new_soup.new_tag('rubrum')
        rubrum.string = rubrum_content
        new_soup.bverfgdokument.entscheidung.append(rubrum)

    tenor_content = [e['content'] for e in output if e['segment'] == "tenor"]
    if len(tenor_content) > 0:
        tenor_content = "\n".join(tenor_content)
        tenor = new_soup.new_tag('tenor')
        tenor.string = tenor_content
        new_soup.bverfgdokument.entscheidung.append(tenor)

    gruende_content = [(e['content'], e['absatzID'], e['rn'], e['ebene1nr'], e['ebene1zeichen'], e['tbeg']) for e in output if e['segment'] == "gruende"]
    has_gruende = len(gruende_content) > 0

    ebene1 = "NA"
    if has_gruende:
        if gruende_content[-1][-1] != "NA":  # last paragraph has a tbeg -> Ebene-1 structure
            # Write Gründe with <ebene1> wrapper tags
            gruende = new_soup.new_tag('gruende')
            new_soup.bverfgdokument.entscheidung.append(gruende)
            for abs_content, absatzID, rn, e_nr, e_zeichen, tbeg in gruende_content:
                # get ebene1 tbeg
                e_tbeg_set = set([abs[-1] for abs in gruende_content if (abs[-1] != "NA" and abs[-3] == e_nr)])
                if e_tbeg_set == set(["tb"]):
                    e_tbeg = "tb"
                elif e_tbeg_set == set(["eg"]):
                    e_tbeg = "eg"
                elif e_tbeg_set == set(["tb","eg"]):
                    e_tbeg = "tbeg"
                else:
                    raise ValueError("Error tbeg annotation")
                
                if ebene1 != e_nr:  # new Ebene-1 section – create wrapper tag
                    ebene1 = e_nr
                    ebe1 = new_soup.new_tag('ebene1')
                    ebe1['nr'] = e_nr
                    ebe1['zeichen'] = e_zeichen
                    ebe1['tbeg'] = e_tbeg
                    new_soup.bverfgdokument.entscheidung.gruende.append(ebe1)
                    current_ebene1 = ebe1
                abs = new_soup.new_tag('absatz')
                abs['absatzID'] = absatzID
                abs['ebene1nr'] = e_nr
                abs['ebene1zeichen'] = e_zeichen
                abs['rn'] = rn
                abs['tbeg'] = tbeg
                abs.string = abs_content
                current_ebene1.append(abs)
        else:
            # Write flat Gründe (no Ebene-1 wrapper tags)
            gruende = new_soup.new_tag('gruende')
            new_soup.bverfgdokument.entscheidung.append(gruende)
            for abs_content, absatzID, rn, e_nr, e_zeichen, e_tbeg in gruende_content:
                gruende = new_soup.new_tag('absatz')
                gruende['absatzID'] = absatzID
                gruende['rn'] = rn
                gruende['tbeg'] = e_tbeg
                gruende.string = abs_content
                new_soup.bverfgdokument.entscheidung.gruende.append(gruende)

    if len(sondervota_output) > 0:
        abw = new_soup.new_tag('abwmeinungen')
        new_soup.bverfgdokument.append(abw)
        for e in sondervota_output:
            abw_abs = new_soup.new_tag('absatz')
            abw_abs['rn'] = e['rn']
            abw_abs.string = e['content']
            new_soup.bverfgdokument.abwmeinungen.append(abw_abs)

    new_soup.prettify()
    with open(path + file.replace(".html", "") + '.xml', 'w', encoding='utf-8') as file:
        file.write(new_soup.prettify())
    return
