#!/usr/bin/env bash
# Compila el APK firmado desde el commit actual (HEAD).
#
# - Exige que no haya cambios sin commitear: cada APK corresponde a un commit exacto.
# - Compila desde una copia limpia (git archive), así el APK nunca incluye .git ni
#   archivos locales que no estén en el repo.
# - Agrega build_info.txt (versión, commit, fecha) que la app muestra en el pie.
#
# Requisitos (ver README):
#   FLET      ejecutable de flet 0.85.3   (por defecto ~/.venvs/timer_aeropuerto/bin/flet)
#   FIRMA_DIR carpeta con la clave de firma, FUERA del repo
#             (por defecto ~/In-data/timer_aeropuerto_firma), con:
#               timer_aeropuerto_release.jks  y  password.txt
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
FLET="${FLET:-$HOME/.venvs/timer_aeropuerto/bin/flet}"
FIRMA_DIR="${FIRMA_DIR:-$HOME/In-data/timer_aeropuerto_firma}"
SALIDA="${SALIDA:-$(dirname "$REPO")/timer_aeropuerto_build}"

cd "$REPO"
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
    echo "ERROR: hay cambios sin commitear. Haz commit antes de compilar." >&2
    exit 1
fi
[[ -x "$FLET" ]] || { echo "ERROR: no encuentro flet en $FLET" >&2; exit 1; }
[[ -f "$FIRMA_DIR/timer_aeropuerto_release.jks" && -f "$FIRMA_DIR/password.txt" ]] || {
    echo "ERROR: falta la clave de firma en $FIRMA_DIR" >&2; exit 1; }

COMMIT="$(git rev-parse HEAD)"
VERSION="$(python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])')"
BUILD_NUMBER="$(python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml","rb"))["tool"]["flet"]["build_number"])')"

# El nombre de la carpeta no importa: el paquete Android sale de [project].name
DIR="$SALIDA/timer_aeropuerto_app"
rm -rf "$DIR"
mkdir -p "$DIR"
git archive HEAD | tar -x -C "$DIR"
rm -f "$DIR/.gitignore" "$DIR/build_apk.sh"
cat > "$DIR/build_info.txt" <<EOF
version=$VERSION
build_number=$BUILD_NUMBER
commit=$COMMIT
fecha=$(date '+%Y-%m-%d %H:%M:%S %z')
EOF

echo "Compilando v$VERSION (build $BUILD_NUMBER) desde ${COMMIT:0:7} en $DIR"
cd "$DIR"
PASS="$(cat "$FIRMA_DIR/password.txt")"
FLET_ANDROID_SIGNING_KEY_STORE_PASSWORD="$PASS" \
FLET_ANDROID_SIGNING_KEY_PASSWORD="$PASS" \
"$FLET" build apk --yes --no-rich-output \
    --android-signing-key-store "$FIRMA_DIR/timer_aeropuerto_release.jks" \
    --android-signing-key-alias upload

APK="$SALIDA/timer_aeropuerto_v${VERSION}_${COMMIT:0:7}.apk"
cp "$DIR/build/apk/timer_aeropuerto_app.apk" "$APK"
echo "APK listo: $APK"
