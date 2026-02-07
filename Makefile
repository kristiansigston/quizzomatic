

run:
	. v/bin/activate && python app.py

qr:
	. v/bin/activate && python generate_qr.py

format:
	. v/bin/activate && autopep8 --in-place --aggressive --aggressive *.py
	. v/bin/activate && djlint templates --reformat
	@files=$$(find static templates -type f \( -name "*.js" -o -name "*.ts" \)); \
	if [ -n "$$files" ]; then \
		npx prettier --write $$files; \
	else \
		echo "No JS/TS files to format."; \
	fi

setup:
	python3 -m venv v
	. v/bin/activate && pip install --upgrade pip
	. v/bin/activate && pip install -r requirements.txt

playwright-install:
	. v/bin/activate && python -m playwright install

screenshot:
	. v/bin/activate && python scripts/take_screenshot.py --url http://localhost:9145 --out /tmp/screenshot.png
