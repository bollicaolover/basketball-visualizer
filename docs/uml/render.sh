#!/usr/bin/env bash
# Renderiza los diagramas UML (.puml -> .png) de la memoria del TFG.
#
# Este entorno no tiene Graphviz (dot), por lo que se usa el motor de
# disposición interno de PlantUML, Smetana (-Playout=smetana), que basta
# para los diagramas de clases, casos de uso y componentes. El de secuencia
# no necesita layout externo.
#
# Tampoco hay Java en el PATH; se reutiliza el JRE que trae MATLAB. Si tienes
# java instalado, basta con exportar JAVA=java antes de ejecutar.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JAVA="${JAVA:-/usr/local/lib/matlab/sys/java/jre/glnxa64/jre/bin/java}"
JAR="$DIR/plantuml.jar"
PLANTUML_VERSION="1.2024.7"

if [[ ! -f "$JAR" ]]; then
  echo "[render] descargando plantuml.jar ($PLANTUML_VERSION)..."
  curl -fsSL -o "$JAR" \
    "https://github.com/plantuml/plantuml/releases/download/v${PLANTUML_VERSION}/plantuml-${PLANTUML_VERSION}.jar"
fi

"$JAVA" -jar "$JAR" -tpng -Playout=smetana -charset UTF-8 \
  "$DIR/casos_de_uso.puml" \
  "$DIR/diagrama_clases.puml" \
  "$DIR/diagrama_secuencia.puml" \
  "$DIR/diagrama_componentes.puml"

echo "[render] listo:"
ls -1 "$DIR"/*.png
