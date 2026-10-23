UV = uv run --python 3.11 --with open3d --with numpy --with scipy --with matplotlib python

demo:
	$(UV) demo/demo.py

.PHONY: demo
