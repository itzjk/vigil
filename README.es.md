# vigil

Los detectores de anomalías de satélite dan demasiadas falsas alarmas. vigil lo mide sobre telemetría real
del OPS-SAT de la ESA (el conjunto público OPSSAT-AD) e implementa una capa de revisión que comprueba cada
alarma antes de que la vea una persona. La línea base está reproducida contra los números publicados; la
capa de revisión funciona de punta a punta pero todavía no tiene detrás un revisor de verdad, así que no
hay ningún resultado de revisión que contar.

Hecho por ZERACK. English version: [`README.md`](README.md).

## Línea base

Seis detectores clásicos del artículo de OPSSAT-AD, reimplementados solo con scikit-learn y corridos sobre
la partición oficial de prueba (529 segmentos, 113 anómalos). «Publicado» es la tabla 3 de Ruszczak et al.,
*Scientific Data* 12, 710 (2025). Cada celda es precisión / exhaustividad / F1.

| Detector | Tipo | Propio, datos actuales | Propio, datos del artículo | Publicado | Falsas alarmas (datos actuales) |
|---|---|---|---|---|---:|
| AdaBoost | supervisado | 0,904 / 0,832 / 0,866 | 0,890 / 0,788 / 0,836 | 0,890 / 0,788 / 0,836 | 10 de 104 alarmas (10 %) |
| LR | supervisado | 0,920 / 0,708 / 0,800 | 0,920 / 0,708 / 0,800 | 0,920 / 0,708 / 0,800 | 7 de 87 (8 %) |
| LSVC | supervisado | 0,911 / 0,726 / 0,808 | 0,911 / 0,726 / 0,808 | 0,911 / 0,726 / 0,808 | 8 de 90 (9 %) |
| IForest | sin supervisión | 0,304 / 0,301 / 0,302 | 0,297 / 0,292 / 0,295 | 0,297 / 0,292 / 0,295 | 78 de 112 (70 %) |
| KNN | sin supervisión | 0,596 / 0,549 / 0,571 | 0,596 / 0,549 / 0,571 | 0,594 / 0,558 / 0,575 | 42 de 104 (40 %) |
| PCA | sin supervisión | 0,364 / 0,354 / 0,359 | 0,367 / 0,354 / 0,360 | 0,360 / 0,354 / 0,357 | 70 de 110 (64 %) |

Las siete métricas del artículo y los conteos de aciertos y fallos están en
[`results/baseline.md`](results/baseline.md).

**Qué cuadra y qué no**

- Con los datos del artículo (la primera versión en Zenodo), AdaBoost, LR, LSVC e IForest salen
  **idénticos** a lo publicado en las siete métricas.
- Con los datos actuales (la versión vigente, la que usa vigil), AdaBoost sube 0,030 en F1 y 0,044 en
  exhaustividad, e IForest 0,007 y 0,009. Causa comprobada: Zenodo cambió tres características
  (`duration`, `gaps_squared`, `var_div_duration`) entre versiones y la tabla del artículo no se recalculó.
- KNN y PCA no cuadran del todo en ninguna versión: KNN da 62 detectadas y 42 falsas alarmas frente a 63 y
  43 publicadas (F1 0,571 frente a 0,575); PCA da 1 o 2 falsas alarmas menos (F1 0,359 o 0,360 frente a
  0,357). Las AUC sí coinciden, así que las puntuaciones son las mismas y lo que se mueve es un segmento
  junto al umbral. Nuestra réplica da exactamente lo mismo que PyOD 1.1.2, la biblioteca que usó el
  artículo, así que la causa probable es otra versión de PyOD o de los datos detrás de esas dos filas. Eso
  no se pudo comprobar.
- LSVC no converge con los parámetros por defecto. Se deja así porque es como se reproduce el artículo.

## Por qué importa

Los detectores que no necesitan etiquetas son los que un operador puede poner de verdad en un satélite
nuevo, y hacen mucho ruido: de los tres reproducidos aquí, entre 4 y 7 de cada 10 alarmas son falsas (70 %
en Isolation Forest, 64 % en PCA, 40 % en KNN), y aun así se les escapa entre el 45 % y el 70 % de las
anomalías reales. Un operador que recibe siete falsas alarmas de cada diez deja de fiarse de la alarma.

Ahí es donde entra una capa de revisión: agentes que toman cada alarma, miran la señal, explican lo que
ven, proponen qué hacer y se lo pasan a una persona que firma. Nada de lo que hay aquí demuestra todavía
que esa capa funcione. Lo que vigil fija es la línea de salida y la regla de medir, para que cualquier
revisor se mida con honestidad: menos falsos positivos, ninguna anomalía perdida de más, misma partición
de prueba y mismo medidor.

## Cómo se corre

```sh
./run.sh
```

Un solo comando: crea el entorno virtual, baja OPSSAT-AD de Zenodo comprobando la suma (unos 20 MB), corre
las pruebas, reproduce la línea base, rehace los ejemplos y pasa el circuito de revisión sobre ellos. Tarda
cerca de minuto y medio y usa menos de 300 MB de memoria. Pide Python 3.9 a 3.12 (se elige con
`PYTHON=/ruta/a/python ./run.sh`).

Para medir cualquier predicción contra la partición de prueba:

```sh
.venv/bin/python measure.py mis_predicciones.csv   # columnas: segment, prediction (0/1) y, opcional, score
```

## Capa de revisión

El circuito que revisa las alarmas está implementado y probado de punta a punta, en `review/`:

- **Expedientes ciegos** (`packet.py`). Por cada alarma que levanta un detector sin supervisión sobre la
  partición de prueba (162 segmentos distintos entre IForest, KNN y PCA) escribe una carpeta con el
  gráfico, las muestras, un resumen numérico (canal, sensor, muestras, duración, mínimo, máximo, saltos,
  huecos) y una hoja de referencia con segmentos nominales del mismo canal, tomados solo de la partición de
  entrenamiento. Un expediente nunca lleva la etiqueta, el número de segmento del conjunto ni horas
  absolutas; una guarda se niega a escribirlo si los lleva y una prueba falla si alguno se cuela. La clave
  que une expediente y segmento vive fuera de los expedientes.
- **Revisores conectables** (`reviewer.py`). Un revisor recibe un expediente y devuelve JSON validado:
  `verdict` (`anomaly`, `nominal` o `unsure`), `confidence` entre 0 y 1, `reason` (una frase que cite algo
  visible: dónde y cuánto) y `next_check`. Hay dos: una regla fija, y un comando externo que se indica con
  `VIGIL_REVIEWER_CMD`, recibe la carpeta del expediente como último argumento e imprime el JSON. Ese es el
  enchufe donde se conecta nuestro sistema de agentes. Una salida mal formada se rechaza y se anota como
  `unsure`; nunca se arregla ni se adivina.
- **Panel de dos revisiones** (`panel.py`). Cada alarma recibe dos revisiones independientes; cada revisor
  trabaja sobre su propia copia del expediente y no ve la respuesta del otro. La regla: **dismissed** solo
  si los dos dicen nominal con confianza de al menos 0,8; **confirmed** si los dos dicen anomalía; todo lo
  demás (desacuerdo, cualquier `unsure`, una revisión rechazada) es **escalated**, a una persona.
- **Registro solo de añadir** (`ledger.py`). Cada expediente, revisión y decisión va a un archivo JSONL con
  hora UTC, versión del revisor y una cadena de sumas, de modo que una línea reescrita se detecta. Es la
  prueba que hace falta antes de dejar en automático cualquier tipo de caso.
- **Medidor** (`score.py`), el único sitio donde entran las etiquetas. Por detector: alarmas antes y
  después, falsas alarmas eliminadas, anomalías reales perdidas por descartar mal, alarmas escaladas a
  persona, y precisión / exhaustividad / F1 antes y después, calculadas con `measure.py`.

```sh
./review.sh --examples              # todo el circuito sobre los 12 segmentos de ejemplo, con la regla fija
./review.sh --test --packets-only   # arma los 162 expedientes de prueba sin revisar nada
./review.sh --test --external       # revisa las alarmas de prueba con el programa de VIGIL_REVIEWER_CMD
```

**El revisor de regla fija es un doble de pruebas.** Compara el mayor salto del segmento con los saltos
nominales del canal y solo existe para comprobar que el circuito funciona. Su salida en
[`results/review_examples.md`](results/review_examples.md) **no es un resultado**: cubre los 12 segmentos
de ejemplo elegidos a mano y descarta mal 2 de las 6 anomalías reales, que es justo la pérdida que el
medidor está para dejar a la vista. El programa se niega a correrlo sobre la partición de prueba.

Un límite conocido del ciego: las muestras son reales, así que un revisor con una copia del conjunto podría
emparejarlas y recuperar la etiqueta. Los revisores deben correr sin el conjunto.

## Ejemplos

[`examples/`](examples/README.md) trae doce segmentos reales, seis anómalos y seis nominales, como gráfico
y como CSV, con una lámina de referencias nominales y las etiquetas aparte en `answers.json`. Enseñan a ojo
cómo es el problema, y sobre ellos corre `./review.sh --examples`.

## Lo que no está hecho

- **No se ha corrido ningún revisor de verdad.** El único revisor usado hasta ahora es el doble de pruebas
  de regla fija, y no se ha revisado nada de la partición de prueba. Aquí no hay evidencia de que revisar
  reduzca las falsas alarmas.
- **La red neuronal del artículo** (FCNN, el mejor modelo publicado, F1 0,946) no está reproducida; vigil
  evita dependencias de aprendizaje profundo. De los 30 algoritmos del artículo hay 6 reproducidos.
- **ESA-ADB**, el conjunto grande de la ESA (11,6 GB comprimido), está documentado en `SOURCES.md` pero ni
  bajado ni usado. Su métrica es F0,5 por evento; `measure.py` solo da F0,5 por segmento.
- OPSSAT-AD es pequeño y de un solo CubeSat: sirve para afinar un método, no para afirmaciones amplias.

## Datos, cita y licencias

- **Código:** MIT, ver [`LICENSE`](LICENSE). Copyright (c) 2026 ZERACK.
- **Datos:** OPSSAT-AD **no se redistribuye** en este repositorio; `download.py` lo baja de Zenodo (DOI
  [10.5281/zenodo.15108715](https://doi.org/10.5281/zenodo.15108715)). La ficha de Zenodo declara CC BY 4.0
  y el archivo de licencia que viene dentro es MIT, (c) 2024 KP Labs. Lo único incluido son los 22
  segmentos de [`examples/`](examples/README.md) (cerca del 1 % del conjunto), con su atribución, la lista
  de cambios y el texto de la licencia original, bajo los términos del conjunto y no bajo la licencia del
  código.
- **Cita a los autores del conjunto** si usas algo de esto: Ruszczak, B., Kotowski, K., Evans, D. y
  Nalepa, J. «The OPS-SAT benchmark for detecting anomalies in satellite telemetry». *Scientific Data* 12,
  710 (2025). <https://doi.org/10.1038/s41597-025-05035-3>
- El detalle, con ESA-ADB (CC BY 3.0 IGO), está en [`SOURCES.md`](SOURCES.md).

vigil es trabajo independiente, sin relación ni aval de la ESA, KP Labs ni los autores del conjunto.
