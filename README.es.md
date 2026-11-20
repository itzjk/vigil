# alarm-guard

Una línea base reproducida de detección de anomalías en telemetría real de satélite (OPS-SAT de la ESA, el
conjunto público OPSSAT-AD), con un medidor único y un pequeño paquete de práctica. Es el suelo para una
capa de revisión que compruebe cada alarma de un detector antes de que la vea una persona; esa capa todavía
no está construida.

Hecho por ZERACK. English version: [`README.md`](README.md).

## Resultado principal

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
- Con los datos actuales (la versión vigente, la que usa este proyecto), AdaBoost sube 0,030 en F1 y 0,044
  en exhaustividad, e IForest 0,007 y 0,009. Causa comprobada: Zenodo cambió tres características
  (`duration`, `gaps_squared`, `var_div_duration`) entre versiones y la tabla del artículo no se recalculó.
- KNN y PCA no cuadran del todo en ninguna versión: KNN da 62 detectadas y 42 falsas alarmas frente a 63 y
  43 publicadas (F1 0,571 frente a 0,575); PCA da 1 o 2 falsas alarmas menos (F1 0,359 o 0,360 frente a
  0,357). Las AUC sí coinciden, así que las puntuaciones son las mismas y lo que se mueve es un segmento
  junto al umbral. Nuestra réplica da exactamente lo mismo que PyOD 1.1.2, la biblioteca que usó el
  artículo, así que la causa probable es otra versión de PyOD o de los datos detrás de esas dos filas. Eso
  no se pudo comprobar.
- LSVC no converge con los parámetros por defecto. Se deja así porque es como se reproduce el artículo.

## Qué significa

Los detectores que no necesitan etiquetas son los que un operador puede poner de verdad en un satélite
nuevo, y hacen mucho ruido: de los tres reproducidos aquí, entre 4 y 7 de cada 10 alarmas son falsas (70 %
en Isolation Forest, 64 % en PCA, 40 % en KNN), y aun así se les escapa entre el 45 % y el 70 % de las anomalías
reales. Un operador que recibe siete falsas alarmas de cada diez deja de fiarse de la alarma.

Ahí es donde entra una capa de revisión: agentes que toman cada alarma, miran la señal, explican lo que
ven, proponen qué hacer y se lo pasan a una persona que firma. Nada de lo que hay aquí demuestra que esa
capa funcione. Este repositorio solo fija la línea de salida y la regla de medir, para que el siguiente
paso se mida con honestidad: menos falsos positivos, ninguna anomalía perdida de más, misma partición de
prueba y mismo medidor.

## Cómo se corre

```sh
./run.sh
```

Un solo comando: crea el entorno virtual, baja OPSSAT-AD de Zenodo comprobando la suma (unos 20 MB), corre
las pruebas del medidor, reproduce la línea base y rehace el paquete de práctica. Tarda cerca de un minuto
y usa unos 220 MB de memoria. Pide Python 3.9 a 3.12 (se elige con `PYTHON=/ruta/a/python ./run.sh`).

Para medir cualquier predicción nueva contra la partición de prueba:

```sh
.venv/bin/python measure.py mis_predicciones.csv   # columnas: segment, prediction (0/1) y, opcional, score
```

## Qué NO está hecho todavía

- **La capa de revisión.** Es el siguiente tramo y no existe. Parte de las alarmas de
  `results/predictions/`.
- **La red neuronal del artículo** (FCNN, el mejor modelo publicado, F1 0,946) no se reprodujo. De los 30
  algoritmos del artículo hay 6 reproducidos.
- **ESA-ADB**, el conjunto grande de la ESA (11,6 GB comprimido), está documentado en `SOURCES.md` pero ni
  bajado ni usado. Su métrica es F0,5 por evento; `measure.py` solo da F0,5 por segmento.
- OPSSAT-AD es pequeño y de un solo CubeSat: sirve para afinar un método, no para afirmaciones amplias.

## Datos, cita y licencias

- **Código:** MIT, ver [`LICENSE`](LICENSE). Copyright (c) 2026 ZERACK.
- **Datos:** OPSSAT-AD **no se redistribuye** en este repositorio; `download.py` lo baja de Zenodo (DOI
  [10.5281/zenodo.15108715](https://doi.org/10.5281/zenodo.15108715)). La ficha de Zenodo declara CC BY 4.0
  y el archivo de licencia que viene dentro es MIT, (c) 2024 KP Labs. Lo único incluido son los 22
  segmentos de [`practice/`](practice/README.md) (cerca del 1 % del conjunto), con su atribución, la lista
  de cambios y el texto de la licencia original, bajo los términos del conjunto y no bajo la licencia del
  código.
- **Cita a los autores del conjunto** si usas algo de esto: Ruszczak, B., Kotowski, K., Evans, D. y
  Nalepa, J. «The OPS-SAT benchmark for detecting anomalies in satellite telemetry». *Scientific Data* 12,
  710 (2025). <https://doi.org/10.1038/s41597-025-05035-3>
- El detalle, con ESA-ADB (CC BY 3.0 IGO), está en [`SOURCES.md`](SOURCES.md).

Trabajo independiente, sin relación ni aval de la ESA, KP Labs ni los autores del conjunto.
