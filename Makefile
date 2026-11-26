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

# Phase 4 — fill the templates with pipeline numbers, then markdown → Word / PDF / PowerPoint
CHROME := /Applications/Google Chrome.app/Contents/MacOS/Google Chrome
report:
	$(PY) src/13_compare_spreadsheet.py
	$(PY) src/14_build_report.py
	dot -Tpng -Gdpi=150 report/er_diagram.dot -o report/er_diagram.png
	dot -Tpng -Gdpi=150 report/pipeline.dot -o report/pipeline.png
	cd report && pandoc report.md -o report.docx --resource-path=.:.. --toc
	cd report && pandoc report.md -o report.html --standalone --embed-resources --css=report.css --resource-path=.:..
	"$(CHROME)" --headless --disable-gpu --no-pdf-header-footer --print-to-pdf=report/report.pdf report/report.html
	cd report && pandoc slides.md -o slides.pptx --resource-path=.:..
	rm -f report/report.html report/report.md report/slides.md   # build leftovers; templates are the source

# Build the submission zip for team "Sata and Dory Letting"
zip:
	rm -f Sata_and_Dory_Letting_FinalSubmission.zip
	zip -r Sata_and_Dory_Letting_FinalSubmission.zip README.md MANUAL_STEPS.md requirements.txt Makefile .env.example \
	    docs src sql notebooks outputs report data/clean data/manual \
	    -x "data/clean/comments.csv" "data/manual/imdb_50k.csv" "*.DS_Store" "report/report.html" "report/report.md" "report/slides.md" "*/.claude/*"

# Start the cleaning log fresh (scripts re-append their own rows on the next run)
reset:
	rm -f outputs/cleaning_log.csv
