# Use the Playwright image that matches your Playwright version
# This image ALREADY contains all fonts and FFMPEG dependencies
FROM mcr.microsoft.com/playwright:v1.40.0-jammy

# 1. Update and install Python 3
RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    rm -rf /var/lib/apt/lists/*

# 2. Set the working directory
WORKDIR /app

# 3. Copy only requirements first (to leverage Docker caching)
COPY requirements.txt .

# 4. Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# 5. Copy the rest of your application code
COPY . .

# 6. Set Environment Variables
# Render uses port 10000 by default for web services
ENV PORT=10000

# 7. Start your application
# Replace 'app:app' with your actual filename and variable (e.g., main:app)
CMD ["python3", "-m", "gunicorn", "-b", "0.0.0.0:10000", "main:app"]