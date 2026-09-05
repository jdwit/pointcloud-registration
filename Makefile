SKILL_DIR ?= $(HOME)/.claude/skills/pointcloud-registration
UV = uv run --python 3.11 --with open3d --with numpy --with scipy --with matplotlib python

demo:
	$(UV) demo/demo.py

install-skill:
	mkdir -p $(SKILL_DIR)
	rsync -a --delete --exclude .git --exclude demo --exclude .github \
		--exclude Makefile --exclude __pycache__ ./ $(SKILL_DIR)/
	@echo "installed to $(SKILL_DIR)"

.PHONY: demo install-skill
