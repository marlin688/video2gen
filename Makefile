.PHONY: setup setup-full test preflight clean

setup:
	pip install -e .
	cd remotion-video && npm install

setup-full:
	pip install -e ".[dev,knowledge,subtitle]"
	cd remotion-video && npm install

test:
	pytest tests/ -v

preflight:
	python -c "from v2g.pipeline import preflight_check, _print_preflight; s, w = preflight_check(); _print_preflight(s, w); print('OK') if s != 'blocked' else None"

clean:
	rm -rf remotion-video/public/voiceover remotion-video/public/slides remotion-video/public/recordings
	rm -f remotion-video/public/source_*.mp4
