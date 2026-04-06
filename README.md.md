# LeadFlow CRM

A lightweight CRM to manage client leads from website contact forms.

## Features
- Track leads with status: New → Contacted → Qualified → Converted / Lost
- Filter by status, source, and search by name/email/company
- Add company name, lead source (website/referral/social/other), and notes
- Live stats dashboard
- Deployable on Render for free

## Folder Structure
```
new crm/
├── templates/
│   └── index.html
├── app.py
├── crm.db          ← auto-created on first run
├── Procfile
├── README.md
├── render.yaml
└── requirements.txt
```

## Run Locally
```bash
pip install -r requirements.txt
python app.py
```
Open http://localhost:5000

## Deploy on Render
1. Push to GitHub
2. New Web Service → connect repo
3. Build: `pip install -r requirements.txt`
4. Start: `gunicorn app:app`
