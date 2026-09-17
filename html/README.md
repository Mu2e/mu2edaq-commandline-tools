# otsdaq CLI walkthrough website

The site is dependency-free and can be opened directly from `index.html` or
served locally:

```bash
python3 -m http.server 8000 --directory html
```

Then open <http://127.0.0.1:8000/>.

Validate page structure, IDs, fragments, and local assets with:

```bash
python3 html/validate.py
node --check html/site.js
```

The five walkthrough pages share `styles.css` and `site.js`. Keep navigation
links consistent across all pages when adding a new chapter.
