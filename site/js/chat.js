// js/chat.js
const sendBtn = document.getElementById('sendBtn');
const queryInput = document.getElementById('queryInput');
const loading = document.getElementById('loading');
const resultsArea = document.getElementById('resultsArea');
const summaryBox = document.getElementById('summary');

const API_URL = 'http://127.0.0.1:5000/api/search'; // Flask backend

async function doSearch() {
  const q = queryInput.value.trim();
  if (!q) return alert('Please enter a query.');
  loading.style.display = 'block';
  resultsArea.innerHTML = '';
  summaryBox.style.display = 'none';
  try {
    const resp = await fetch(API_URL, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ query: q, top_k: 3 })
    });
    const data = await resp.json();
    if (data.error) {
      resultsArea.innerHTML = `<div class="result-block">Error: ${data.error}</div>`;
      return;
    }
    // show summary
    summaryBox.style.display = 'block';
    summaryBox.innerText = data.summary;

    // per-doc results
    const results = data.results;
    for (const doc of Object.keys(results)) {
      const block = document.createElement('div');
      block.className = 'result-block';
      block.innerHTML = `<div class="doc-title">${doc}</div>`;
      const rows = results[doc];
      if (!rows || rows.length === 0) {
        block.innerHTML += `<div class="snippet">No pages matched in this document.</div>`;
      } else {
        rows.forEach(it => {
          const a = document.createElement('a');
          // local file names are relative to the site folder:
          let fileName = (doc === 'PMBOK') ? 'PMBOK7.pdf' : (doc === 'PRINCE2') ? 'PRINCE2.pdf' : 'ISO21500.pdf';
          a.href = `${fileName}#page=${it.page_no}`;
          a.target = '_blank';
          a.className = 'page-link';
          a.innerText = `Open page ${it.page_no}`;
          const s = document.createElement('div');
          s.className = 'snippet';
          s.innerHTML = `<div>${it.text_snippet}</div><div style="margin-top:.4rem">${a.outerHTML} • score: ${it.score}</div>`;
          block.appendChild(s);
        });
      }
      resultsArea.appendChild(block);
    }

  } catch (err) {
    resultsArea.innerHTML = `<div class="result-block">Request failed: ${err.message}</div>`;
  } finally {
    loading.style.display = 'none';
  }
}

sendBtn.addEventListener('click', doSearch);
queryInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') doSearch(); });
