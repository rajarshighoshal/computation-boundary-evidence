PYTHON ?= python3
LATEX ?= pdflatex
BIBTEX ?= $(shell command -v bibtex 2>/dev/null || command -v bibtex.original 2>/dev/null)

.PHONY: all analyze figures pdf clean
all: figures pdf

analyze:
	$(PYTHON) scripts/analyze_results.py
	$(PYTHON) scripts/analyze_visual_results.py

figures: analyze
	$(PYTHON) scripts/make_figures.py

pdf:
	$(LATEX) -no-shell-escape -interaction=nonstopmode -halt-on-error main.tex
	$(BIBTEX) main
	$(LATEX) -no-shell-escape -interaction=nonstopmode -halt-on-error main.tex
	$(LATEX) -no-shell-escape -interaction=nonstopmode -halt-on-error main.tex

clean:
	rm -f main.aux main.log main.out main.blg main.fdb_latexmk main.fls main.synctex.gz
