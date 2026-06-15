#!/usr/bin/env bash
set -ex

apt-get update
apt-get install -y python3.10 python3-pip python3-dev

python3.10 -m pip install -U pip
python3.10 -m pip install --break-system-packages {requirements}

echo "Setup complete"
