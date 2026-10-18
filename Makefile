PY ?= python3

.PHONY: all data warehouse quality dashboard notebooks

all: data warehouse quality dashboard notebooks

data:
	$(PY) pipeline/download.py
	$(PY) pipeline/ingest.py

warehouse:
	$(PY) pipeline/transform.py

quality:
	$(PY) pipeline/quality_checks.py

dashboard:
	$(PY) pipeline/export_dashboard.py

notebooks:
	cd notebooks && jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=1800 *.ipynb
