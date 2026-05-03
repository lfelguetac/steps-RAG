#!/bin/bash
set -e

echo "Building Lambda packages..."

for func in trigger extract chunk embed index query notify; do
  echo "Packaging $func..."
  cd functions/$func

  if [ -f requirements.txt ]; then
    pip install -r requirements.txt -t . --upgrade 2>/dev/null
  fi

  zip -r ../../infra/$func.zip . -x "*.pyc" "__pycache__/*" "*.zip" 2>/dev/null
  cd ../..
done

echo "Build complete."
