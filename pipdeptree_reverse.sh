#!/bin/sh
# Regenerates detailed_requirements.txt, requirements.txt, and reverse_dependency.txt
# from requirements.in.  This mirrors exactly what the GitHub Actions workflow does.
#
# Prerequisites: pip install pip-tools pipdeptree
# Usage:         sh pipdeptree_reverse.sh

set -e

# 1. Compile pinned dependencies
pip-compile --output-file=detailed_requirements.txt requirements.in

# 2. Remove self-referential comment lines added by pip-compile
#    (portable sed: macOS needs '' after -i, Linux does not)
case "$(uname -s)" in
  Darwin) sed -i '' '/^    #   -r requirements.in/d' detailed_requirements.txt ;;
  *)      sed -i    '/^    #   -r requirements.in/d' detailed_requirements.txt ;;
esac

# 3. Derive a flat pinned list (no comments, no extras like [parquet])
grep -v "^[[:space:]]*#" detailed_requirements.txt \
  | grep -v "^[[:space:]]*$" \
  | sed 's/\[[^]]*\]//g' \
  > requirements.txt

# 4. Install so pipdeptree can inspect the environment
pip install -r requirements.txt

# 5. Build reverse dependency tree
grep -v "^#" requirements.txt \
  | grep -v "^$" \
  | cut -d'=' -f1 \
  | xargs -I {} sh -c \
      'echo "=== {} ===" && pipdeptree --reverse --packages {} 2>/dev/null && echo ""' \
  > reverse_dependency.txt
