## How to generate a `requirements.txt`that has no dependency conflict:
1. In an external environment, use the commands to start a python dev Docker container
```bash
docker run --rm -it \
  --platform linux/amd64 \
  -v "$(pwd)":/workspace \
  -w /workspace \
  mcr.microsoft.com/devcontainers/python:3.11 \
  /bin/bash
```

## Install Python packages dependency management tools
```bash
pip install pipdeptree
pip install pip-tools
```
Note: ensure pip version is <26 to be compatible with pip-tools

2. Prepare the `requirements.in` that we want to test the updates
3. Run the command to generate the `detailed_requirements.txt` which will show which packages are installed due to what other packages
    ```bash
    pip-compile --output-file=detailed_requirements.txt requirements.in
    ```
4. Clean away the lines "    #   -r requirements.in"
    ```bash
    sed -i '/^    #   -r requirements.in/d' detailed_requirements.txt
    ```
5. Pipe only the packages without remarks to a clean `requirements.txt`
    ```bash
    grep -v "^[[:space:]]*#" detailed_requirements.txt | grep -v "^[[:space:]]*$" > requirements.txt
    sed -i 's/\[[^]]*\]//g' requirements.txt
    ```
    This way the `.txt` file is clean and can be used to replace the one in this repository to track what has been changed.

## How to generate the reverse dependency tree file `reverse_dependency.txt`

Using `requirements.txt` as input, find out what is the required version range for each package using pipdeptree

```bash
cat requirements.txt | grep -v "^#" | grep -v "^$" | cut -d'=' -f1 | xargs -I {} sh -c 'echo "=== {} ===" && pipdeptree --reverse --packages {} 2>/dev/null && echo ""' > reverse_dependency.txt
```
**Note:**
pipdeptree reverse sometimes not able to pick up what is the parent library, hence we can check the detailed_requirements.txt generated using the pip-tools (pip-compile command) 
