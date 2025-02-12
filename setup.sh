#!/usr/bin/env bash
set -e  # Exit immediately if a command exits with a non-zero status

echo "Setting up the Teserex Blockchain environment..."

# 1. Create virtual environment (if not already created)
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi

# 2. Activate the virtual environment
source venv/bin/activate

# 3. Upgrade pip and install system dependencies
pip3 install --upgrade pip setuptools wheel
sudo apt install -y build-essential libyaml-dev
sudo apt  install cargo
sudo apt-get install -y build-essential cmake clang python3-dev libssl-dev rustc
sudo apt install python3-pytest
sudo apt  install rustup
rustup default stable
# 4. Install required dependencies
pip3 install -r requirements.txt || {
  echo "Error installing dependencies. Check error messages above."
  exit 1
}

echo "Setup complete! To activate the virtual environment, run:"
echo "source venv/bin/activate"

# 'pip list' to see all pip packages installed
# 'pytest tests' to run the unit tests