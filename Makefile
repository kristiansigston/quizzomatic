

run:
	. v/bin/activate && python app.py

qr:
	. v/bin/activate && python generate_qr.py

format:
	. v/bin/activate && autopep8 --in-place --aggressive --aggressive *.py

setup:
	python3 -m venv v
	. v/bin/activate && pip install --upgrade pip
	. v/bin/activate && pip install -r requirements.txt

playwright-install:
	. v/bin/activate && python -m playwright install

screenshot:
	. v/bin/activate && python scripts/take_screenshot.py --url http://localhost:5000 --out /tmp/screenshot.png
