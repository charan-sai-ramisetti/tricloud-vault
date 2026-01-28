# TriCloud Vault

TriCloud Vault is a multi-cloud storage platform that allows users to securely upload and manage files across **AWS S3**, **Azure Blob Storage**, and **Google Cloud Storage**. The platform features **pay-as-you-go billing**, **UPI payment integration**, and a fully automated **DevOps pipeline** powered by **Terraform**, **Docker**, **Ansible**, and **GitHub Actions**.

## 🚀 Key Features

- **Multi-Cloud Storage**
  - Choose where to store your files: AWS, Azure, or GCP
  - Secure uploads using signed URLs
  - User-specific folder isolation

- **Pay-As-You-Go Billing**
  - Razorpay UPI integration
  - Usage-based credits system
  - Automated usage tracking (storage + requests)

- **Authentication**
  - Secure JWT-based login and signup
  - User dashboard with usage insights

- **DevOps & Automation**
  - Infrastructure as Code (Terraform)
  - Automated EC2 provisioning
  - Ansible-based server configuration
  - Dockerized backend service
  - CI/CD pipeline using GitHub Actions
  - Domain + SSL support

- **Frontend**
  - Lightweight **HTML + CSS + JavaScript** UI
  - Simple and intuitive dashboard

## 🧱 Tech Stack

**Frontend:**  
HTML, CSS, JavaScript  

**Backend:**  
FastAPI (or Django), PostgreSQL, Cloud SDKs (boto3, azure-storage-blob, google-cloud-storage)

**Cloud Providers:**  
AWS, Azure, Google Cloud Platform

**DevOps:**  
Terraform, Ansible, Docker, GitHub Actions

## 📦 Modules

- `backend/` → API service  
- `frontend/` → UI pages  
- `infra/terraform/` → Cloud infrastructure  
- `infra/ansible/` → Server configuration  
- `docker/` → Docker & Nginx setup  
- `.github/workflows/` → CI/CD pipelines  

## 📄 Project Goal

TriCloud Vault demonstrates real-world cloud engineering concepts by combining:
- Multi-cloud architecture  
- IAAC  
- Payment systems  
- Automated deployment  
- Production-grade backend  

This project is designed to showcase strong **Cloud**, **DevOps**, and **Backend Engineering** skills.

---

## 📜 License
This project is for educational and demonstration purposes.
