# One command rebuilds everything:  make all
# Each target runs the scripts for one stage, in order.
# PY points at the project's virtual environment so everyone uses the same package versions.

PY := .venv/bin/python

.PHONY: all setup smoke collect clean spark sql charts report zip reset

all: collect clean spark sql charts report

setup:
	uv venv --python 3.12 .venv
	uv pip install --python $(PY) -r requirements.txt

smoke:
	$(PY) src/00_smoke_test.py

# Phase 2 — pull raw data and flatten it
collect:
	$(PY) src/01_collect_wikipedia.py
	$(PY) src/02_collect_tmdb.py
	$(PY) src/03_collect_youtube.py
	$(PY) src/04_flatten_json.py

# Phase 3 — match names, fix types, score sentiment
clean:
	$(PY) src/05_match_films.py
	$(PY) src/06_clean_typecast.py
	$(PY) src/07_sentiment.py

spark:
	$(PY) src/08_spark_text_job.py

sql:
	$(PY) src/09_load_mysql.py

charts:
	$(PY) src/10_analysis.py
	$(PY) src/11_charts.py
	$(PY) src/12_documentation_tables.py

# Phase 4 — markdown → Word / PDF / PowerPoint with pandoc
report:
	dot -Tpng -Gdpi=150 report/er_diagram.dot -o report/er_diagram.png
	cd report && pandoc report.md -o report.docx --resource-path=.:..
	cd report && pandoc report.md -o report.pdf --resource-path=.:.. || echo "PDF needs a LaTeX engine; the .docx is the main output"
	cd report && pandoc slides.md -o slides.pptx --resource-path=.:..

# Start the cleaning log fresh (scripts re-append their own rows on the next run)
reset:
	rm -f outputs/cleaning_log.csv
