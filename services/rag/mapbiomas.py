"""Pinned MapBiomas Indonesia evidence and local lexical retrieval for GeoLLM."""

import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from services.rag.ingestion.pipeline import TextExtractor

SITE = "https://landy.mapbiomas.id"
RAW = Path("data/raw/knowledge/mapbiomas-indonesia")
INDEX = Path("data/curated/knowledge/mapbiomas-indonesia/index.json")
COMMIT = "a957d72992d90ed5a4787ce13c8a36b7a1b48780"
DOCS = {
    "R01": ("ATBD Collection 4.1", "en", "4.1", "/assets/files/ATBD%20Mapbiomas%20ID%20Col%204.1%20EN.pdf"),
    "R02": ("ATBD Collection 4.1", "id", "4.1", "/assets/files/ATBD%20Mapbiomas%20ID%20Col%204.1%20ID.pdf"),
    "R03": ("Legend Description Collection 4.1", "en", "4.1", "/assets/files/Col%204.1%20-%20Legend%20Description%20EN.pdf"),
    "R04": ("Legend Code (linked by Collection 4.1)", "en+id", "4 (linked for 4.1)", "/assets/legendcode/Integration%20and%20Layers%20MB%20Indonesia%20-%20Col%204%20-%20EN%20.pdf"),
    "R05": ("Glossary", "en", "portal snapshot", "/en/glossary"),
    "R06": ("Accuracy Assessment", "en", "2.0", "/en/accuracy-assessment"),
    "R07": ("Reference Maps", "en", "portal snapshot", "/en/refmap"),
    "R08": ("Terms of Use", "en", "portal snapshot", "/en/termsofuse"),
    "R09": ("Fact Sheet Collection 4.1", "en", "4.1", "/storage/files/%5BEN%5D%20Fact%20sheet%20%20Indonesia%20Land%20Cover%20Collection%204.1.pdf"),
    "R10": ("FAQ", "en", "portal snapshot", "/en/faq"),
    "R11": ("Infographics catalogue", "en", "portal snapshot", "/en/infographics"),
    "R12": ("Public gap-fill script", "en", COMMIT, f"https://raw.githubusercontent.com/mapbiomas-indonesia/MapBiomas-Indonesia---Landy/{COMMIT}/4.0/4.1%20Filtering/Gap%20filled%20filter.js"),
    "R13": ("ATBD Collection 3.0", "id", "3.0", "/assets/files/ATBD%20MapBiomas%20ID%20Col%203.0.pdf"),
    "R14": ("Google Earth Engine access", "en", "portal snapshot", "/en/gee"),
}
TERMS = {
    "맹그로브": "mangrove", "양식장": "aquaculture tambak", "논": "rice paddy sawah", "팜유": "oil palm sawit",
    "목재조림": "pulpwood plantation kebun kayu", "참조지도": "reference map", "참조 지도": "reference map",
    "보완": "gap fill", "결측": "gap fill", "후처리": "post classification filter", "정확도": "accuracy assessment",
    "범례": "legend", "용어": "glossary", "이용조건": "terms license", "재배포": "license redistribute",
    "공간 필터": "spatial filter", "시간 필터": "temporal filter", "수관": "canopy", "산림": "forest hutan",
}
MAX_BYTES = 32 * 1024 * 1024


class SourceTable(HTMLParser):
    """Keep the official table cells and the reference URL separately."""

    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = None
        self.cell = None
        self.uri = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
            self.uri = None
        if tag in {"td", "th"} and self.row is not None:
            self.cell = []
        if tag == "a" and self.cell is not None:
            href = dict(attrs).get("href", "")
            if href.startswith("https://"):
                self.uri = href

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.cell is not None:
            self.row.append(" ".join(" ".join(self.cell).split()))
            self.cell = None
        if tag == "tr" and self.row is not None:
            self.rows.append((self.row, self.uri))
            self.row = None


def structured(documents):
    facts = {"glossary": [], "reference_maps": [], "legend": []}
    for doc in documents:
        source = {key: doc[key] for key in ("id", "url", "raw_sha256")}
        if doc["id"] in {"R05", "R07"}:
            parser = SourceTable()
            parser.feed(Path(doc["raw_path"]).read_text(encoding="utf-8"))
            for row, uri in parser.rows:
                if doc["id"] == "R05" and len(row) == 3 and row[1] == ":":
                    facts["glossary"].append({"term": row[0], "definition": row[2], "source": source})
                if doc["id"] == "R07" and len(row) == 4 and re.fullmatch(r"\d{4}", row[1]):
                    facts["reference_maps"].append({"layer": row[0], "year": int(row[1]), "institution": row[3],
                                                    "provider_url": uri, "source": source})
        if doc["id"] == "R04":
            text = " ".join(chunk["text"] for chunk in doc["chunks"])
            for label, code in (("Mangrove", 5), ("Aquaculture", 31), ("Rice Paddy", 40),
                                ("Oil Palm", 35), ("Pulpwood Plantation", 9)):
                match = re.search(rf"{label}.{{0,65}}?\b{code}\s+(#[0-9a-fA-F]{{6}})", text, re.IGNORECASE)
                if match:
                    facts["legend"].append({"class": label, "pixel_code": code, "color": match[1], "page": 1, "source": source})
    return facts


def fetch(doc_id, entry):
    title, language, version, path = entry
    url = path if path.startswith("https://") else SITE + path
    kind = ".pdf" if url.endswith(".pdf") else ".js" if url.endswith(".js") else ".html"
    request = Request(url, headers={"User-Agent": "SDSS evidence catalogue/1.0"})
    with urlopen(request, timeout=40) as response:
        if urlsplit(response.geturl()).hostname != urlsplit(url).hostname:
            raise ValueError("MAPBIOMAS_SOURCE_REDIRECT_INVALID")
        raw = response.read(MAX_BYTES + 1)
    if not 0 < len(raw) <= MAX_BYTES or (kind == ".pdf" and not raw.startswith(b"%PDF-")):
        raise ValueError("MAPBIOMAS_SOURCE_FORMAT_OR_SIZE_INVALID")
    digest = sha256(raw).hexdigest()
    source = RAW / f"{doc_id}-{digest}{kind}"
    if not source.is_file():
        source.write_bytes(raw)
    if kind == ".pdf":
        from pypdf import PdfReader

        pages = [(i + 1, page.extract_text() or "") for i, page in enumerate(PdfReader(source).pages)]
    else:
        value = raw.decode("utf-8", errors="strict")
        if kind == ".html":
            parser = TextExtractor()
            parser.feed(value)
            value = "".join(parser.parts).partition("MapBiomas Indonesia - Landy")[-1]
            if not value.strip():
                value = "".join(parser.parts)
            value = re.split(r"Co-creators|Co-Creators|Co creators", value, maxsplit=1)[0]
        pages = [(None, value)]
    chunks = []
    for page, text in pages:
        text = " ".join(text.split())
        for start in range(0, len(text), 800):
            passage = text[start:start + 1000]
            if passage:
                chunks.append({"page": page, "offset": start, "text": passage})
    if not chunks:
        raise ValueError("MAPBIOMAS_NO_EXTRACTED_TEXT")
    return {"id": doc_id, "title": title, "version": version, "language": language, "url": url,
            "retrieved_at": datetime.now(timezone.utc).isoformat(), "raw_sha256": digest, "raw_path": source.as_posix(),
            "bytes": len(raw), "priority": "P0" if doc_id <= "R09" else "P1", "chunks": chunks}


def build():
    RAW.mkdir(parents=True, exist_ok=True)
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    documents, failures = [], {}
    previous = {doc["id"]: doc for doc in json.loads(INDEX.read_bytes())["documents"]} if INDEX.is_file() else {}

    def acquire(key, entry):
        doc = previous.get(key)
        if doc is not None and doc["version"] == entry[2]:
            path = Path(doc["raw_path"])
            if path.is_file() and sha256(path.read_bytes()).hexdigest() == doc["raw_sha256"]:
                return doc
        return fetch(key, entry)

    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {key: pool.submit(acquire, key, entry) for key, entry in DOCS.items()}
        for key, job in jobs.items():
            try:
                document = job.result()
                documents.append(document)
                print(key, document["bytes"], len(document["chunks"]), flush=True)
            except (OSError, ValueError) as error:
                failures[key] = str(error)
                print(key, "unavailable", failures[key], flush=True)
    pending = INDEX.with_suffix(".pending.json")
    pending.write_text(json.dumps({"documents": documents, "unavailable": failures,
                                  "structured_knowledge": structured(documents)}, ensure_ascii=False), encoding="utf-8")
    pending.replace(INDEX)


@lru_cache(maxsize=32)
def checked(path, _size, _mtime_ns):
    return sha256(path.read_bytes()).hexdigest()


def catalog(store):
    path = store.safe_path(INDEX)
    if not path.is_file():
        return {"status": "KNOWLEDGE_CORPUS_PENDING", "documents": [], "structured_counts": {}}
    bundle = json.loads(path.read_bytes())
    visible = ("id", "title", "language", "version", "url", "retrieved_at", "raw_sha256", "priority")
    return {"status": "INDEXED", "documents": [{key: doc[key] for key in visible} for doc in bundle["documents"]],
            "structured_counts": {key: len(rows) for key, rows in bundle.get("structured_knowledge", {}).items()},
            "unavailable": bundle["unavailable"]}


def search(store, question):
    path = store.safe_path(INDEX)
    if not path.is_file():
        return {"status": "KNOWLEDGE_CORPUS_PENDING", "citations": [], "answer": None}
    bundle = json.loads(path.read_bytes())
    tokens = set(re.findall(r"[\w]+", question.lower())) - {"the", "is", "and", "for", "mapbiomas", "indonesia", "what", "apa", "yang"}
    for term, alias in TERMS.items():
        if term in question:
            tokens.update(alias.split())
    evidence_tokens = tokens - {"glossary", "legend", "reference", "maps", "atbd", "collection", "범례", "용어", "참조", "지도"}
    if not evidence_tokens:
        evidence_tokens = tokens
    found = []
    intent = set()
    for source_id, phrases in {
        "R03": ("legend", "범례", "정의"), "R04": ("code", "코드"), "R05": ("glossary", "용어"),
        "R06": ("assessment", "정확도"), "R07": ("reference map", "참조 지도", "참조지도"),
        "R08": ("license", "재배포", "이용조건"), "R09": ("fact sheet", "팩트시트"),
        "R11": ("infographic", "인포그래픽"), "R12": ("github", "스크립트"), "R13": ("3.0", "collection 3"),
    }.items():
        if any(word in question.lower() for word in phrases):
            intent.add(source_id)
    for doc in bundle["documents"]:
        if doc["id"] < "R10" or doc["id"] in {"R10", "R14"} or doc["id"] in intent:
            for chunk in doc["chunks"]:
                words = set(re.findall(r"[\w]+", chunk["text"].lower()))
                matches = evidence_tokens & words
                if matches:
                    found.append((len(matches) + 4 * (doc["id"] in intent), doc, chunk, matches))
    citations, used = [], set()
    for _, doc, chunk, matches in sorted(found, key=lambda row: -row[0]):
        key = (doc["id"], chunk["page"])
        if key in used:
            continue
        source = store.safe_path(doc["raw_path"])
        try:
            info = source.stat()
            valid = info.st_size == doc["bytes"] and checked(source, info.st_size, info.st_mtime_ns) == doc["raw_sha256"]
        except OSError:
            valid = False
        if not valid:
            continue
        used.add(key)
        text = chunk["text"]
        first_word = max(matches, key=lambda word: (len(word), word))
        match = text.lower().find(first_word)
        start = max(0, match - 45)
        page = chunk["page"]
        citations.append({"id": doc["id"], "title": doc["title"], "version": doc["version"], "language": doc["language"],
                          "page": page, "text_offset": chunk["offset"] + start, "excerpt": text[start:start + 180],
                          "url": doc["url"] + (f"#page={page}" if page else ""), "source_sha256": doc["raw_sha256"]})
        if len(citations) == 5:
            break
    return {"status": "FOUND" if citations else "NO_MATCH", "mode": "local_lexical_evidence", "answer": None,
            "documents": len(bundle["documents"]), "p0_documents": sum(doc["priority"] == "P0" for doc in bundle["documents"]),
            "unavailable": bundle["unavailable"], "citations": citations}


if __name__ == "__main__":
    build()
