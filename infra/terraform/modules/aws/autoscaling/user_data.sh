#!/bin/bash

sudo apt update -y
sudo apt install python3-pip git -y

cd /home/ubuntu

git clone https://github.com/charan-sai-ramisetti/tricloud-vault.git

cd tricloud-vault/backend

python3 -m venv env
. env/bin/activate
cd tri_cloud_vault

pip install -r requirements.txt

python manage.py migrate

python manage.py collectstatic --noinput

nohup python manage.py runserver 0.0.0.0:8000 &