FROM python:3.10-slim

# កំណត់ទីតាំងធ្វើការនៅក្នុង Container
WORKDIR /app

# ចម្លងឯកសារ requirements.txt ចូល
COPY requirements.txt .

# ដំឡើង dependencies ដែលមាននៅក្នុង requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# ចម្លងកូដទាំងអស់ (រួមទាំង bot.py) ចូលទៅក្នុង Container
COPY . .

# បញ្ជាឱ្យដំណើរការ Bot ពេល Container ដើរ
CMD ["python", "bot.py"]
