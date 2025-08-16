# setup.sh (Initial setup script)
#!/bin/bash

echo "Setting up Word Heist Backend..."

# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file from template
cp .env.example .env

# Initialize database
flask init-db

# Seed puzzles for 30 days
flask seed-puzzles

echo "Setup complete! Run 'flask run' to start the development server."

# docker-compose.yml (Optional - for local development with PostgreSQL)
version: '3.8'

services:
  web:
    build: .
    ports:
      - "5000:5000"
    environment:
      - DATABASE_URL=postgresql://wordheist:password@db:5432/wordheist
      - SECRET_KEY=dev-secret-key
    depends_on:
      - db
    volumes:
      - .:/app

  db:
    image: postgres:15
    environment:
      - POSTGRES_USER=wordheist
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=wordheist
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

volumes:
  postgres_data:

