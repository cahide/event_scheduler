.PHONY: install run dev clean env

# install all dependencies
install:
	pip install -r requirements.txt

# copy .env template if .env doesn't exist yet
env:
	@if not exist .env copy .env.example .env

# start the chatbot UI
run:
	chainlit run app.py

# start with hot-reload (nice for development)
dev:
	chainlit run app.py -w

# remove generated files
clean:
	if exist __pycache__ rmdir /s /q __pycache__
	if exist .chainlit rmdir /s /q .chainlit
