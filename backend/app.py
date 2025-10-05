# app.py
# Local backend for comparing PMBOK7, PRINCE2, and ISO PDFs with accurate page linking

import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from PyPDF2 import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
import numpy as np

# --------------------------------------------------
# Configuration
# --------------------------------------------------
SITE_PDF_FOLDER = os.path.join(os.path.dirname(__file__), "..", "site")
PDF_FILES = {
    "PMBOK": os.path.join(SITE_PDF_FOLDER, "PMBOK7.pdf"),
    "PRINCE2": os.path.join(SITE_PDF_FOLDER, "PRINCE2.pdf"),
    "ISO21500": os.path.join(SITE_PDF_FOLDER, "ISO21500.pdf"),
}
TOP_K = 3

app = Flask(__name__)
CORS(app)

pages_data = []
doc_page_index = {}

# --------------------------------------------------
# Helpers
# --------------------------------------------------
def extract_pages_text(pdf_path):
    """Extract text per page safely."""
    reader = PdfReader(pdf_path)
    pages = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        text = " ".join(text.split())
        pages.append((i + 1, text))
    return pages


def build_index():
    """Read all PDFs and build TF-IDF index."""
    global pages_data, doc_page_index, vectorizer, tfidf_matrix
    pages_data = []
    doc_page_index = {}
    all_texts = []

    for doc_key, path in PDF_FILES.items():
        if not os.path.exists(path):
            print(f"[warning] PDF not found: {path}")
            doc_page_index[doc_key] = []
            continue
        pages = extract_pages_text(path)
        indices = []
        for (pno, text) in pages:
            entry = {"doc_key": doc_key, "page_no": pno, "text": text}
            indices.append(len(pages_data))
            pages_data.append(entry)
            all_texts.append(text if text.strip() else "[no-text-on-page]")
        doc_page_index[doc_key] = indices

    vectorizer = TfidfVectorizer(stop_words="english", max_df=0.9)
    if all_texts:
        tfidf_matrix = vectorizer.fit_transform(all_texts)
    else:
        tfidf_matrix = None

    print(f"✅ Indexed {len(pages_data)} pages across {len(PDF_FILES)} documents.")


# --------------------------------------------------
# Routes
# --------------------------------------------------
@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "indexed_pages": len(pages_data)})


@app.route("/api/search", methods=["POST"])
def api_search():
    """
    Input JSON:  { "query": "some text" }
    Output: { "results": {doc_name: [{page_no, score, link, snippet}, ...]}, "summary": "..." }
    """
    data = request.json or {}
    query = data.get("query", "").strip()
    top_k = int(data.get("top_k", TOP_K))

    if not query:
        return jsonify({"error": "empty query"}), 400
    if tfidf_matrix is None:
        return jsonify({"error": "Index not built or PDFs missing."}), 500

    qvec = vectorizer.transform([query])
    cosine_similarities = linear_kernel(qvec, tfidf_matrix).flatten()

    results = {}
    snippets_for_summary = {}

    for doc_key, indices in doc_page_index.items():
        if not indices:
            results[doc_key] = []
            continue

        idxs = np.array(indices)
        scores = cosine_similarities[idxs]
        top_idx_order = scores.argsort()[::-1][:top_k]
        items = []

        pdf_filename = os.path.basename(PDF_FILES[doc_key])

        for rank_pos in top_idx_order:
            page_idx = idxs[rank_pos]
            score = float(scores[rank_pos])
            text = pages_data[page_idx]["text"]
            pno = pages_data[page_idx]["page_no"]

            # 🔗 Build precise link that HTML can open
            pdf_link = f"{pdf_filename}#page={pno}"

            snippet = (text[:600] + "...") if len(text) > 600 else text
            items.append({
                "page_no": pno,
                "score": round(score, 4),
                "text_snippet": snippet,
                "pdf_link": pdf_link,
            })

        results[doc_key] = items
        snippets_for_summary[doc_key] = " ".join([it["text_snippet"] for it in items])

    summary = synthesize_summary(query, snippets_for_summary)

    return jsonify({
        "query": query,
        "results": results,
        "summary": summary
    })


def synthesize_summary(query, snippets_for_doc):
    """Generate a simple comparative summary."""
    q_tokens = set([t.lower() for t in query.split() if len(t) > 2])
    doc_scores = {}
    for doc, text in snippets_for_doc.items():
        tokens = set([w.lower().strip(".,()") for w in text.split() if len(w) > 2])
        overlap = len(q_tokens & tokens)
        doc_scores[doc] = overlap

    ranked = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
    lines = [f"Comparative summary for query: “{query}”."]
    if ranked and ranked[0][1] > 0:
        lines.append("Documents with strongest relevance: " + ", ".join([d for d, _ in ranked]) + ".")
    else:
        lines.append("No clear dominant document found; all provide contextual relevance.")

    for doc, _ in ranked:
        snippet = snippets_for_doc.get(doc, "")
        if snippet.strip():
            short = (snippet[:200] + "...") if len(snippet) > 200 else snippet
            lines.append(f"{doc}: {short}")

    lines.append("Note: Click on the document links to view the relevant PDF pages.")
    return " ".join(lines)


# --------------------------------------------------
# Main
# --------------------------------------------------
if __name__ == "__main__":
    build_index()
    app.run(host="127.0.0.1", port=5000, debug=False)
