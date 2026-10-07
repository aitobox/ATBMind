#!/usr/bin/env bash
# ==============================================================================
# ATBDraw Nuitka Cross-Platform Standalone Build Script
# Packages ATBDraw (PySide6 + ATBMind Core + Draw Plugin) into native binaries.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "${SCRIPT_DIR}")"
cd "${PROJECT_ROOT}"

OUTPUT_DIR="${PROJECT_ROOT}/dist"
DRY_RUN=false
MACOS_APP=false

# Detect OS
OS_NAME="$(uname -s)"
case "${OS_NAME}" in
    Darwin*)
        MACOS_APP=true
        ;;
    Linux*|MINGW*|MSYS*|CYGWIN*)
        MACOS_APP=false
        ;;
    *)
        MACOS_APP=false
        ;;
esac

# Parse options
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --output-dir=*)
            OUTPUT_DIR="${1#*=}"
            shift
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--dry-run] [--output-dir=DIR]"
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

echo "=== ATBDraw Nuitka Standalone Builder ==="
echo "Project Root: ${PROJECT_ROOT}"
echo "Output Dir:   ${OUTPUT_DIR}"
echo "Target OS:    ${OS_NAME}"

# Verify required files
ENTRYPOINT="apps/atbmind_desktop/main.py"
SEED_TEMPLATES="skills/image_generation/templates/seed_templates.json"
CONFIG_FILE="configs/config.yaml"

for req_file in "${ENTRYPOINT}" "${SEED_TEMPLATES}" "${CONFIG_FILE}"; do
    if [[ ! -f "${req_file}" ]]; then
        echo "Error: Required file not found: ${req_file}" >&2
        exit 1
    fi
done

# Assemble Nuitka parameters
NUITKA_ARGS=(
    --standalone
    --enable-plugin=pyside6
    --include-package=atbmind_core
    --include-package=apps
    --include-package=skills
    --include-package=roles
    --include-data-files="${SEED_TEMPLATES}=${SEED_TEMPLATES}"
    --include-data-files="${CONFIG_FILE}=${CONFIG_FILE}"
    --output-dir="${OUTPUT_DIR}"
    --output-filename="ATBMind"
    --remove-output
)

if [[ "${MACOS_APP}" == "true" ]]; then
    NUITKA_ARGS+=(
        --macos-create-app-bundle
        --macos-app-name="ATBMind"
    )
fi

NUITKA_CMD=("python" "-m" "nuitka" "${NUITKA_ARGS[@]}" "${ENTRYPOINT}")

if [[ "${DRY_RUN}" == "true" ]]; then
    echo "[DRY-RUN] Verified dependencies and build targets."
    echo "[DRY-RUN] Command to execute:"
    printf '%q ' "${NUITKA_CMD[@]}"
    echo ""
    echo "[DRY-RUN] Check completed successfully."
    exit 0
fi

# Check nuitka installation
if ! python -m nuitka --version &>/dev/null; then
    echo "Nuitka not found in current environment. Installing nuitka..."
    pip install -q nuitka
fi

echo "Starting Nuitka standalone compilation..."
mkdir -p "${OUTPUT_DIR}"
"${NUITKA_CMD[@]}"

echo "=== Build finished successfully! Artifacts placed in: ${OUTPUT_DIR} ==="
