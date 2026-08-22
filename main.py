import os
import base64
import json
import re
import requests

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

import storage


# ============================================================
# 1. CONFIGURACIÓN
# ============================================================

load_dotenv()

API_KEY = os.getenv("NVIDIA_API_KEY")

if not API_KEY:
    print("❌ ERROR: NVIDIA_API_KEY no está configurada en .env")
    raise SystemExit(1)


NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

MODEL = "nvidia/nemotron-nano-12b-v2-vl"


# ============================================================
# 2. CREAR FASTAPI
# ============================================================

app = FastAPI(
    title="PlantMedic IA",
    version="1.0"
)


storage.init_db()


# ============================================================
# 3. CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 3.1 ARCHIVOS ESTÁTICOS (FOTOS GUARDADAS)
# ============================================================

app.mount(
    "/uploads",
    StaticFiles(directory=storage.UPLOADS_DIR),
    name="uploads"
)


# ============================================================
# 4. RUTAS DE PRUEBA
# ============================================================

@app.get("/")
def raiz():

    return {
        "mensaje": "PlantMedic IA — Backend funcionando ✅"
    }


@app.get("/health")
def health():

    return {
        "status": "ok",
        "modelo": MODEL
    }


# ============================================================
# 5. CREAR PROMPT
# ============================================================

def create_analysis_prompt(
    image_base64: str,
    mime_type: str
) -> dict:

    prompt = """
ERES UN ESPECIALISTA EN ENTOMOLOGÍA, FITOPATOLOGÍA, BOTÁNICA
Y CUIDADO DE PLANTAS ORNAMENTALES Y MEDICINALES.

Tu tarea es analizar visualmente la fotografía proporcionada para:

1. Identificar, en la medida de lo posible, la planta (ornamental
   o medicinal) y sus características generales.

2. Determinar si la planta presenta una plaga, enfermedad,
   marchitez u otro problema visible.

El objetivo principal del sistema es detectar PLAGAS,
pero también debes reconocer otros problemas visibles de la planta
y aportar información botánica útil sobre la especie observada.

IMPORTANTE:

- Analiza únicamente lo que realmente puede observarse en la imagen.
- NO inventes plagas, enfermedades ni síntomas.
- NO afirmes una causa si la imagen no proporciona evidencia suficiente.
- Si existe incertidumbre sobre el problema, utiliza el estado "inconcluso".
- NO inventes datos botánicos si la planta no puede identificarse
  con una confianza razonable.

============================================================
0. IDENTIFICACIÓN DE LA PLANTA
============================================================

Antes de evaluar el problema, intenta identificar la planta
observada. Puede ser una planta ORNAMENTAL (ej. rosa, geranio,
petunia) o MEDICINAL (ej. manzanilla, aloe vera, menta, ruda,
hierbabuena, sábila, orégano).

Debes reportar:

- "nombre_planta": nombre común más probable en español
  (ej. "Rosa", "Aloe vera / Sábila", "Menta").

- "nombre_cientifico": nombre científico (binomio latino)
  si puede determinarse con confianza razonable
  (ej. "Rosa spp.", "Aloe vera", "Mentha spicata").

- "familia": familia botánica
  (ej. "Rosaceae", "Asphodelaceae", "Lamiaceae").

- "caracteristicas": objeto con información general de la especie
  (no solo de la foto puntual, sino de la planta como especie):

    - "hoja": forma y tipo de hoja característico de la especie
      (ej. "Hojas ovaladas, bordes dentados, color verde intenso").

    - "tallo": tipo de tallo característico
      (ej. "Tallo leñoso y espinoso", "Tallo herbáceo y carnoso").

    - "epoca": época de floración o crecimiento característica
      (ej. "Primavera a verano", "Todo el año en climas cálidos").

    - "clima": clima o condiciones ambientales que prefiere
      (ej. "Templado a cálido, requiere buena luz solar").

    - "riego": forma de riego recomendada para la especie
      (ej. "Riego moderado, dejar secar el sustrato entre riegos").

REGLAS DE IDENTIFICACIÓN:

- Si reconoces la especie o al menos el género con confianza
  razonable, completa todos los campos con la mejor información
  botánica general disponible para esa especie.

- Si NO puedes identificar la planta con confianza razonable
  (imagen poco clara, especie no reconocible, o la imagen no
  muestra una planta), utiliza:

    "nombre_planta": "No identificada"
    "nombre_cientifico": "No disponible"
    "familia": "No disponible"

  y en "caracteristicas" utiliza "Información no disponible"
  en cada campo.

- NO inventes un nombre científico o familia si no estás
  razonablemente seguro. Es preferible indicar que no se
  identificó la planta.

============================================================
1. BUSCA PRIMERO PLAGAS O INSECTOS VISIBLES
============================================================

PULGONES

Busca:

- Insectos pequeños de cuerpo blando.
- Pueden ser verdes, negros, amarillos, marrones o rosados.
- Suelen aparecer agrupados o formando colonias.
- Frecuentes en brotes jóvenes.
- Tallos tiernos.
- Botones florales.
- Envés de las hojas.

------------------------------------------------------------

ÁCAROS / ARAÑA ROJA

Busca:

- Pequeños puntos rojizos, amarillos o claros.
- Telarañas extremadamente finas.
- Punteado amarillo o blanquecino en las hojas.
- Pérdida localizada de color.

IMPORTANTE:

Una hoja amarilla por sí sola NO significa que existan ácaros.

------------------------------------------------------------

COCHINILLAS

Busca:

- Masas blancas de aspecto algodonoso.
- Pequeños bultos adheridos a tallos u hojas.
- Formaciones blancas, marrones o grisáceas.
- Acumulaciones en las uniones entre hojas y tallos.

------------------------------------------------------------

TRIPS

Busca:

- Insectos pequeños y alargados.
- Marcas plateadas en hojas o pétalos.
- Raspaduras visibles.
- Pequeños puntos oscuros asociados.

------------------------------------------------------------

MOSCA BLANCA

Busca:

- Pequeños insectos blancos.
- Presencia principalmente en el envés de las hojas.
- Grupos de pequeños insectos blancos.

------------------------------------------------------------

ORUGAS / GUSANOS

Busca:

- Larvas visibles.
- Agujeros irregulares.
- Bordes de hojas mordidos.
- Pérdida visible de tejido vegetal.

------------------------------------------------------------

ESCARABAJOS

Busca:

- Insectos visibles de cuerpo duro.
- Perforaciones en hojas.
- Mordidas visibles.

------------------------------------------------------------

HORMIGAS

La presencia de hormigas por sí sola NO significa
que exista una plaga.

Sin embargo, si aparecen junto con colonias de pulgones
o melaza, pueden servir como evidencia secundaria.

============================================================
2. BUSCA SIGNOS INDIRECTOS DE PLAGAS
============================================================

Busca:

- Melaza brillante o pegajosa.
- Fumagina negra asociada a melaza.
- Colonias visibles.
- Hojas deformadas alrededor de insectos.
- Brotes enrollados.
- Agujeros visibles.
- Mordidas.
- Telarañas muy finas.
- Daño localizado alrededor de insectos.

IMPORTANTE:

Los síntomas indirectos por sí solos NO siempre demuestran
la existencia de una plaga.

Por ejemplo:

- Una hoja amarilla NO significa automáticamente ácaros.
- Una hoja deformada NO significa automáticamente pulgones.
- Una mancha NO significa automáticamente una plaga.
- Una flor marchita NO significa automáticamente una plaga.

Debes buscar evidencia visual consistente.

============================================================
3. BUSCA MARCHITEZ O ESTRÉS
============================================================

Analiza también si la flor o la planta está marchita.

Busca signos como:

- Flores caídas.
- Flores marchitas.
- Pétalos secos.
- Pétalos arrugados.
- Pétalos retraídos.
- Hojas caídas.
- Hojas flácidas.
- Tallos doblados.
- Tallos con pérdida de firmeza.
- Bordes secos.
- Aspecto general decaído.
- Pérdida de turgencia.

IMPORTANTE:

LA MARCHITEZ NO SIGNIFICA AUTOMÁTICAMENTE QUE EXISTA UNA PLAGA.

Puede estar relacionada con:

- Falta de agua.
- Exceso de agua.
- Calor intenso.
- Estrés ambiental.
- Problemas de drenaje.
- Problemas en las raíces.
- Envejecimiento natural de la flor.
- Enfermedad.
- Daño físico.

Si observas marchitez claramente pero NO observas
insectos ni evidencia de infestación:

usa:

"status": "enfermedad_posible"

y:

"tipo_problema": "Marchitez o estrés hídrico"

En la descripción explica únicamente los signos visibles.

NO asegures que la causa es falta de agua si eso
no puede determinarse mediante la fotografía.

============================================================
4. BUSCA POSIBLES ENFERMEDADES
============================================================

OIDIO

Busca:

- Polvo blanco visible.
- Apariencia similar a harina.
- Presencia en hojas, tallos o brotes.

------------------------------------------------------------

MILDIU

Busca:

- Manchas amarillas u oscuras.
- Posible polvillo en el envés.

------------------------------------------------------------

ROYA

Busca:

- Puntos anaranjados.
- Puntos marrones.
- Pústulas visibles.

------------------------------------------------------------

ANTRACNOSIS

Busca:

- Manchas necróticas.
- Bordes oscuros.
- Posibles halos amarillos.

------------------------------------------------------------

BOTRYTIS

Busca:

- Podredumbre visible.
- Tejido marrón.
- Crecimiento gris o algodonoso.
- Daño especialmente visible en flores.

------------------------------------------------------------

POSIBLES PROBLEMAS BACTERIANOS O VIRALES

Busca:

- Manchas irregulares.
- Halos acuosos.
- Patrones de mosaico.
- Deformaciones severas.

IMPORTANTE:

No asegures una enfermedad específica si la fotografía
no proporciona suficiente evidencia.

Si existen signos de enfermedad pero no puedes identificar
con suficiente confianza la causa exacta, utiliza un nombre
general como:

"Posible enfermedad foliar"

============================================================
5. PROBLEMAS NUTRICIONALES O AMBIENTALES
============================================================

Busca:

- Clorosis.
- Amarillamiento entre venas.
- Bordes secos.
- Necrosis.
- Coloración anormal.
- Crecimiento debilitado.
- Quemaduras visibles.

IMPORTANTE:

No diagnostiques una deficiencia nutricional específica
únicamente por el color de una hoja.

Si existe evidencia compatible pero no puede determinarse
la causa exacta, utiliza:

"Posible estrés nutricional o ambiental"

============================================================
6. ORDEN OBLIGATORIO DEL ANÁLISIS
============================================================

Analiza SIEMPRE en este orden:

1. ¿La imagen realmente muestra una planta o una parte de una planta?

2. ¿La imagen tiene suficiente calidad para analizarla?

3. ¿Hay insectos o plagas visibles?

4. ¿Hay signos indirectos claramente compatibles con una plaga?

5. ¿Hay marchitez visible?

6. ¿Hay signos compatibles con una enfermedad?

7. ¿Hay signos de estrés ambiental o nutricional?

8. Determina el problema principal visible.

============================================================
7. CLASIFICACIÓN DEL STATUS
============================================================

Usa EXACTAMENTE uno de estos valores:

"sin_problemas"

"plagas_presentes"

"enfermedad_posible"

"inconcluso"

------------------------------------------------------------
SIN PROBLEMAS
------------------------------------------------------------

Utiliza:

"status": "sin_problemas"

cuando:

- La planta tiene apariencia saludable.
- No hay insectos visibles.
- No existen signos claros de infestación.
- No hay marchitez significativa.
- No existen signos evidentes de enfermedad.

En este caso utiliza:

"tipo_problema": "Ninguno"

------------------------------------------------------------
PLAGAS PRESENTES
------------------------------------------------------------

Utiliza:

"status": "plagas_presentes"

SOLAMENTE cuando:

- Se observan insectos claramente visibles.

O:

- Existe evidencia visual fuerte y característica
  de una plaga específica.

Ejemplos de tipo_problema:

"Pulgones"

"Ácaros"

"Cochinillas"

"Trips"

"Mosca blanca"

"Orugas"

"Escarabajos"

Si observas claramente una plaga diferente,
puedes indicar su nombre.

NO utilices "plagas_presentes" solamente por:

- Amarillamiento.
- Manchas.
- Marchitez.
- Hojas secas.
- Flores secas.

------------------------------------------------------------
ENFERMEDAD POSIBLE
------------------------------------------------------------

Utiliza:

"status": "enfermedad_posible"

cuando:

- Existe marchitez clara sin evidencia de insectos.
- Existen manchas compatibles con enfermedad.
- Se observa crecimiento fúngico.
- Existe podredumbre visible.
- Hay síntomas claros que no corresponden a una plaga.
- Existe estrés nutricional o ambiental visible.

Ejemplos de tipo_problema:

"Marchitez o estrés hídrico"

"Oidio"

"Roya"

"Botrytis"

"Posible enfermedad foliar"

"Posible estrés nutricional o ambiental"

------------------------------------------------------------
INCONCLUSO
------------------------------------------------------------

Utiliza:

"status": "inconcluso"

cuando:

- La imagen está borrosa.
- La imagen está demasiado oscura.
- La imagen está tomada desde demasiado lejos.
- No se observa claramente la zona afectada.
- Los posibles insectos son demasiado pequeños.
- Los síntomas son ambiguos.
- No existe suficiente evidencia para determinar el problema.
- La imagen NO muestra una planta.

Si la imagen no muestra una planta, utiliza:

"tipo_problema": "No se observa una planta"

Si la imagen muestra una planta pero no tiene suficiente calidad:

"tipo_problema": "Imagen no concluyente"

============================================================
8. PROBLEMA
============================================================

La propiedad:

"tipo_problema"

representa el PROBLEMA PRINCIPAL que será mostrado al usuario
bajo el título "Diagnóstico".

Cuando exista evidencia suficiente, sé específico: si puedes
identificar razonablemente la enfermedad o plaga exacta
(por ejemplo "Mancha Negra (Diplocarpon rosae)", "Oidio",
"Pulgones"), inclúyela. Si solo puedes determinar una categoría
general, usa un nombre general.

Debe ser corta y directa.

Ejemplos:

"Pulgones"

"Ácaros"

"Cochinillas"

"Marchitez o estrés hídrico"

"Oidio"

"Posible enfermedad foliar"

"Posible estrés nutricional o ambiental"

"Ninguno"

"Imagen no concluyente"

"No se observa una planta"

NO escribas explicaciones largas dentro de tipo_problema.

============================================================
9. DIAGNÓSTICO (SÍNTOMAS OBSERVADOS)
============================================================

La propiedad:

"observation"

será mostrada en la interfaz como:

"Diagnóstico"

Por lo tanto, debe presentarse como los SÍNTOMAS OBSERVADOS
en la imagen: qué se ve, exactamente, que sustenta el diagnóstico.

Describe únicamente características visibles.

Sé específico y desarrolla cada síntoma con un poco de
detalle (no solo el nombre del síntoma, también su
apariencia, ubicación en la planta y extensión aproximada).
Cuando existan varios síntomas distintos, enuméralos dentro
del mismo texto en forma de lista breve (por ejemplo
separados por punto y seguido), en vez de una sola oración
genérica.

Usa aproximadamente 3 a 5 síntomas, redactados como
oraciones completas (no solo palabras sueltas).

Ejemplo correcto:

"Manchas circulares o irregulares de color negro o marrón
oscuro, de bordes difusos, distribuidas en varias hojas.
Amarillamiento (clorosis) progresivo alrededor de las
manchas. Los síntomas aparecen primero en las hojas
inferiores y más viejas, y se extienden hacia las hojas
superiores. Algunas hojas afectadas muestran inicio de
caída prematura."

Ejemplo correcto:

"Numerosos insectos pequeños de cuerpo blando y color verde,
agrupados en colonia densa alrededor de los brotes jóvenes y
del botón floral. Se observa una sustancia brillante y
pegajosa (melaza) sobre las hojas cercanas. Los brotes más
afectados muestran ligera deformación."

Ejemplo correcto:

"Pétalos caídos, arrugados y con pérdida visible de firmeza
en la flor principal. Las hojas cercanas conservan buen
color y turgencia. No se observan insectos visibles ni
señales claras de infestación en tallos u hojas."

Ejemplo incorrecto:

"La planta tiene pulgones porque está amarilla."

NO inventes características que no puedan observarse.

============================================================
9.1 DESCRIPCIÓN GENERAL DEL PROBLEMA
============================================================

La propiedad:

"descripcion_general"

será mostrada en la interfaz como:

"Descripción del problema", y es DISTINTA de "observation".

Mientras que "observation" describe lo que se ve EN ESTA
FOTO específica, "descripcion_general" es información
EDUCATIVA general sobre el tipo de problema identificado
(la plaga, enfermedad o condición en sí): qué es, cómo se
comporta o por qué ocurre, y qué efecto suele tener sobre
la planta en general. No repitas la descripción de síntomas
de esta foto; da contexto general sobre el problema.

Usa 2 a 4 oraciones.

Ejemplo (para Cochinillas):

"Las cochinillas son insectos chupadores de savia que se
agrupan en tallos y hojas, protegidos por una cubierta
cerosa blanca. Debilitan la planta al alimentarse de su
savia y, con el tiempo, pueden causar deformaciones y
favorecer la aparición de fumagina, un hongo negro que
crece sobre la melaza que excretan."

Ejemplo (para Mancha Negra):

"La mancha negra es una enfermedad fúngica muy común en
rosales, causada por el hongo Diplocarpon rosae. Se
propaga con humedad prolongada sobre el follaje y puede
debilitar significativamente la planta si no se controla,
llegando a causar defoliación."

Ejemplo (para estado "sin_problemas"):

"No se identificó ninguna plaga ni enfermedad específica
que describir; la planta no presenta signos de problemas
en este momento."

Si el estado es "inconcluso" y no se identificó un problema
específico, usa un texto breve indicando que no hay un
problema concreto que describir todavía.

NO inventes datos biológicos o científicos que no sean
razonablemente conocidos o consistentes con el problema
identificado.

============================================================
10. SOLUCIÓN (TRATAMIENTO)
============================================================

La propiedad:

"recommendation"

será mostrada en la interfaz como:

"Tratamiento", y debe redactarse como el TRATAMIENTO a
aplicar AHORA para atender el problema ya detectado (no
medidas preventivas a futuro, eso va en "prevention").

IMPORTANTE — FORMATO: "recommendation" es un ARRAY (lista)
de 3 a 5 strings en JSON, NO un solo texto largo. Cada
elemento del array es UN paso de tratamiento, redactado
como una oración completa, concreta y accionable. Ejemplo
de formato (no de contenido):

"recommendation": [
    "Primer paso concreto.",
    "Segundo paso concreto.",
    "Tercer paso concreto."
]

Cada paso debe ser:

- Claro y concreto (una acción por elemento).
- Práctico, en orden lógico (qué hacer primero, luego qué).
- Seguro.
- Apropiado para una planta ornamental o medicinal doméstica,
  sin asumir que el usuario tiene herramientas o productos
  profesionales.

Para PLAGAS puedes recomendar:

- Aislar temporalmente la planta.
- Revisar el envés de las hojas.
- Retirar manualmente insectos.
- Lavar suavemente con agua.
- Utilizar jabón potásico siguiendo las instrucciones
  del producto.

Para MARCHITEZ puedes recomendar:

- Revisar la humedad del sustrato.
- Revisar la frecuencia de riego.
- Comprobar que exista buen drenaje.
- Evitar exposición excesiva al calor.
- Retirar flores completamente secas.

Para ENFERMEDADES puedes recomendar:

- Retirar y destruir (no compostar) las partes afectadas.
- Desinfectar herramientas de poda entre cortes.
- Mejorar ventilación.
- Evitar mantener hojas constantemente húmedas.
- Fungicidas orgánicos de uso doméstico (azufre, cobre/caldo
  bordelés, bicarbonato de sodio), siguiendo las instrucciones
  del producto.
- Consultar con un especialista si el problema continúa.

Para una IMAGEN INCONCLUSA:

- Solicitar una fotografía más cercana.
- Pedir mejor iluminación.
- Recomendar fotografiar hojas, tallos, brotes,
  flores o la zona afectada.

NO recomiendes:

- Mezclas químicas peligrosas.
- Sustancias tóxicas caseras.
- Dosis específicas de pesticidas fuertes.
- Acciones peligrosas para el usuario.

============================================================
10.1 PREVENCIÓN
============================================================

La propiedad:

"prevention"

será mostrada en la interfaz como:

"Prevención", y debe indicar cómo EVITAR que el problema
vuelva a ocurrir o cómo mantener la planta sana hacia
adelante (a diferencia de "recommendation", que es la
acción inmediata sobre el problema ya presente).

IMPORTANTE — FORMATO: "prevention" es también un ARRAY
(lista) de 3 a 5 strings en JSON, igual que "recommendation".
Cada elemento es UN consejo preventivo, redactado como
oración completa. Ejemplo de formato (no de contenido):

"prevention": [
    "Primer consejo preventivo.",
    "Segundo consejo preventivo.",
    "Tercer consejo preventivo."
]

ESTE CAMPO ES OBLIGATORIO Y NUNCA PUEDE QUEDAR VACÍO (nunca
un array vacío ni elementos que digan "no disponible" o "no
aplica"), EXCEPTO en el único caso de que la imagen no
muestre una planta en absoluto. Incluso si el estado es
"sin_problemas" o "inconcluso" sobre una planta real, DEBES
dar consejos de cuidado preventivo igualmente.

Cada consejo debe ser concreto, redactado como oración
completa, no solo palabras sueltas. Basa los consejos en la
especie identificada cuando sea posible (usando
"caracteristicas", por ejemplo su riego o clima preferido),
y en el tipo de problema detectado. Ejemplos según el caso:

- Elegir variedades resistentes al identificar la especie.
- Regar en la base evitando mojar el follaje; regar en la
  mañana para que el follaje seque durante el día.
- Mantener buen espaciado y ventilación entre plantas.
- Retirar hojas caídas y malezas alrededor de la planta.
- Fertilización equilibrada, evitando exceso de nitrógeno.
- Inspeccionar la planta regularmente (hojas, envés, brotes)
  para detectar problemas a tiempo.
- Ajustar el riego según la especie identificada (frecuencia
  y cantidad).

Si el estado es "sin_problemas", usa este campo para dar
consejos de cuidado preventivo general apropiados para la
especie identificada (o generales de buen cuidado si no se
identificó la especie).

Si el estado es "inconcluso" pero SÍ se observa una planta,
da consejos generales de cuidado preventivo aplicables
mientras se logra un diagnóstico más claro.

NO repitas literalmente el mismo contenido de "recommendation".

============================================================
11. FORMATO DE RESPUESTA
============================================================

RESPONDE ÚNICAMENTE CON JSON VÁLIDO.

NO utilices Markdown.

NO escribas ```json.

NO escribas ```.

NO agregues explicaciones antes del JSON.

NO agregues explicaciones después del JSON.

UTILIZA EXACTAMENTE ESTA ESTRUCTURA:

{
    "status": "sin_problemas|plagas_presentes|enfermedad_posible|inconcluso",
    "nombre_planta": "nombre común de la planta o 'No identificada'",
    "nombre_cientifico": "nombre científico o 'No disponible'",
    "familia": "familia botánica o 'No disponible'",
    "caracteristicas": {
        "hoja": "forma/tipo de hoja característico",
        "tallo": "tipo de tallo característico",
        "epoca": "época de floración o crecimiento",
        "clima": "clima o condiciones que prefiere",
        "riego": "forma de riego recomendada"
    },
    "tipo_problema": "nombre breve del problema",
    "observation": "síntomas observados en la imagen",
    "descripcion_general": "información educativa general sobre el problema identificado",
    "recommendation": ["paso 1 del tratamiento", "paso 2 del tratamiento", "paso 3 del tratamiento"],
    "prevention": ["consejo preventivo 1", "consejo preventivo 2", "consejo preventivo 3"]
}

NO agregues la propiedad "severidad".

NO agregues ninguna propiedad adicional fuera de las indicadas.

============================================================
12. EJEMPLOS
============================================================

EJEMPLO 1 - PULGONES EN ROSA (ORNAMENTAL)

{
    "status": "plagas_presentes",
    "nombre_planta": "Rosa",
    "nombre_cientifico": "Rosa spp.",
    "familia": "Rosaceae",
    "caracteristicas": {
        "hoja": "Hojas compuestas, folíolos ovalados con bordes aserrados y superficie brillante.",
        "tallo": "Tallo leñoso, con espinas.",
        "epoca": "Floración principal en primavera y verano.",
        "clima": "Templado, requiere buena exposición solar.",
        "riego": "Riego moderado y regular, evitando encharcamiento."
    },
    "tipo_problema": "Pulgones",
    "observation": "Numerosos insectos pequeños de cuerpo blando y color verde, agrupados en colonia densa alrededor de los brotes jóvenes y del botón floral. Se observa una sustancia brillante y ligeramente pegajosa (melaza) sobre las hojas cercanas a la colonia. Algunos brotes afectados muestran una leve deformación en su punta de crecimiento.",
    "descripcion_general": "Los pulgones son insectos chupadores de savia que se reproducen rápidamente y forman colonias densas en tejido joven. Debilitan la planta al alimentarse de su savia, pueden transmitir virus entre plantas y su melaza favorece la aparición de fumagina, un hongo negro superficial.",
    "recommendation": [
        "Aísla temporalmente la planta para evitar que la plaga se propague a otras cercanas.",
        "Revisa cuidadosamente los brotes y el envés de las hojas, ya que los pulgones suelen esconderse ahí.",
        "Retira los pulgones con un chorro suave de agua, repitiendo el proceso cada 2 a 3 días.",
        "Si la colonia persiste después de varios lavados, aplica jabón potásico siguiendo las instrucciones del producto.",
        "Evita el uso de insecticidas fuertes en interiores o cerca de niños y mascotas."
    ],
    "prevention": [
        "Inspecciona los brotes nuevos semanalmente, ya que los pulgones prefieren el tejido tierno.",
        "Evita el exceso de fertilizante nitrogenado, pues favorece un crecimiento blando que atrae a esta plaga.",
        "Mantén buen espaciado entre plantas para favorecer la ventilación y dificultar la propagación.",
        "Controla la presencia de hormigas cerca de la planta, ya que suelen 'cuidar' colonias de pulgones por la melaza que producen."
    ]
}

------------------------------------------------------------

EJEMPLO 2 - MANCHA NEGRA EN ROSA (ENFERMEDAD)

{
    "status": "enfermedad_posible",
    "nombre_planta": "Rosa",
    "nombre_cientifico": "Rosa spp.",
    "familia": "Rosaceae",
    "caracteristicas": {
        "hoja": "Hojas compuestas, folíolos ovalados con bordes aserrados y superficie brillante.",
        "tallo": "Tallo leñoso, con espinas.",
        "epoca": "Floración principal en primavera y verano.",
        "clima": "Templado, requiere buena exposición solar.",
        "riego": "Riego moderado y regular, evitando encharcamiento."
    },
    "tipo_problema": "Mancha Negra (Diplocarpon rosae)",
    "observation": "Manchas circulares o irregulares de color negro o marrón oscuro, de bordes difusos, distribuidas en varias hojas de la planta. Amarillamiento (clorosis) progresivo en el tejido alrededor de las manchas. Los síntomas aparecen primero en las hojas inferiores y más viejas, y se extienden gradualmente hacia las hojas superiores. Algunas de las hojas más afectadas muestran inicio de caída prematura.",
    "descripcion_general": "La mancha negra es una enfermedad fúngica muy común en rosales, causada por el hongo Diplocarpon rosae. Se propaga con humedad prolongada sobre el follaje, especialmente en climas templados y húmedos, y puede debilitar significativamente la planta si no se controla, llegando a causar defoliación importante.",
    "recommendation": [
        "Retira y destruye (no compostes) todas las hojas que muestren manchas, ya que las esporas del hongo pueden sobrevivir en materia vegetal.",
        "Poda las ramas más afectadas o débiles, desinfectando las tijeras con alcohol entre cada corte para no propagar el hongo.",
        "Mejora la circulación de aire alrededor de la planta despejando follaje muy denso.",
        "Si los síntomas persisten o avanzan, aplica un fungicida orgánico de uso doméstico (a base de azufre, cobre o bicarbonato de sodio) siguiendo estrictamente las instrucciones del producto.",
        "Repite el tratamiento cada 7 a 14 días mientras persistan los síntomas."
    ],
    "prevention": [
        "Riega en la base de la planta evitando mojar el follaje, preferiblemente temprano en la mañana para que las hojas sequen durante el día.",
        "Mantén buen espaciado entre plantas para favorecer la ventilación y reducir la humedad sobre las hojas.",
        "Retira regularmente hojas caídas y restos vegetales del suelo, ya que pueden albergar esporas del hongo.",
        "Al replantar en el futuro, considera variedades de rosa conocidas por su resistencia a esta enfermedad."
    ]
}

------------------------------------------------------------

EJEMPLO 3 - SÁBILA CON MARCHITEZ (MEDICINAL)

{
    "status": "enfermedad_posible",
    "nombre_planta": "Aloe vera / Sábila",
    "nombre_cientifico": "Aloe vera",
    "familia": "Asphodelaceae",
    "caracteristicas": {
        "hoja": "Hojas carnosas, alargadas, en roseta, con bordes dentados.",
        "tallo": "Tallo corto, casi imperceptible bajo la roseta de hojas.",
        "epoca": "Crecimiento activo todo el año en climas cálidos.",
        "clima": "Cálido y seco, tolera sequía, requiere buena luz.",
        "riego": "Riego escaso y espaciado, dejar secar el sustrato por completo entre riegos."
    },
    "tipo_problema": "Marchitez o estrés hídrico",
    "observation": "Pérdida de firmeza y arrugamiento visible en varias hojas, que aparecen más delgadas y con la superficie hundida. El color general de la planta se mantiene verde, sin manchas ni decoloración. No se observan insectos ni telarañas ni signos claros de infestación en hojas o tallo.",
    "descripcion_general": "El estrés hídrico ocurre cuando la planta recibe agua de forma inadecuada, ya sea en exceso o por defecto. En especies suculentas como el Aloe vera, el exceso de riego es la causa más frecuente, ya que sus hojas almacenan agua y son sensibles a la pudrición de raíz cuando el sustrato permanece húmedo por mucho tiempo.",
    "recommendation": [
        "Revisa la frecuencia y cantidad de riego, ya que tanto el exceso como la falta de agua son causas comunes de este síntoma en esta especie.",
        "Retira la planta de su maceta y comprueba el estado de la raíz y del sustrato; si está muy húmedo o compactado, deja secar antes de volver a regar.",
        "Verifica que la maceta tenga orificios de drenaje funcionando correctamente.",
        "Si el sustrato está completamente seco desde hace mucho tiempo, aplica un riego moderado y observa la recuperación en los próximos días."
    ],
    "prevention": [
        "Deja secar el sustrato por completo entre riegos, ya que esta especie tolera bien la sequía y es sensible al exceso de agua.",
        "Usa una maceta con buen drenaje y, si es posible, un sustrato específico para suculentas o cactáceas.",
        "Evita ubicarla en zonas donde se acumule agua o humedad constante.",
        "Ajusta la frecuencia de riego según la estación: menos riego en meses fríos o de menor luz."
    ]
}

------------------------------------------------------------

EJEMPLO 4 - PLANTA SALUDABLE

{
    "status": "sin_problemas",
    "nombre_planta": "Menta",
    "nombre_cientifico": "Mentha spicata",
    "familia": "Lamiaceae",
    "caracteristicas": {
        "hoja": "Hojas ovaladas, bordes dentados, superficie rugosa y aromática.",
        "tallo": "Tallo herbáceo, cuadrangular, rastrero o erecto.",
        "epoca": "Crecimiento activo en primavera y verano.",
        "clima": "Templado, prefiere semisombra y humedad constante.",
        "riego": "Riego frecuente, manteniendo el sustrato húmedo sin encharcar."
    },
    "tipo_problema": "Ninguno",
    "observation": "La planta presenta una apariencia general saludable, con hojas de color verde uniforme y buena turgencia. No se observan insectos, telarañas ni masas algodonosas en tallos ni en el envés de las hojas. No hay manchas, decoloración ni deformaciones visibles.",
    "descripcion_general": "No se identificó ninguna plaga ni enfermedad específica que describir; la planta no presenta signos de problemas en este momento.",
    "recommendation": [
        "Continúa con el cuidado habitual que le has estado dando, ya que actualmente no presenta ningún problema visible.",
        "Revisa periódicamente hojas, tallos, brotes y flores para detectar cualquier cambio a tiempo.",
        "No es necesario aplicar ningún tratamiento en este momento."
    ],
    "prevention": [
        "Mantén el sustrato húmedo de forma constante, sin encharcar, ya que esta especie prefiere humedad estable.",
        "Ubícala en semisombra, evitando el sol directo intenso durante varias horas seguidas.",
        "Inspecciona semanalmente el envés de las hojas y las uniones con el tallo, zonas donde suelen iniciar las plagas.",
        "Mejora la ventilación alrededor de la planta si el follaje está muy denso."
    ]
}

------------------------------------------------------------

EJEMPLO 5 - IMAGEN NO CONCLUYENTE

{
    "status": "inconcluso",
    "nombre_planta": "No identificada",
    "nombre_cientifico": "No disponible",
    "familia": "No disponible",
    "caracteristicas": {
        "hoja": "Información no disponible",
        "tallo": "Información no disponible",
        "epoca": "Información no disponible",
        "clima": "Información no disponible",
        "riego": "Información no disponible"
    },
    "tipo_problema": "Imagen no concluyente",
    "observation": "La fotografía no muestra suficiente detalle para identificar con confianza la planta ni la presencia de una plaga, enfermedad u otro problema.",
    "descripcion_general": "No hay un problema específico identificado todavía; se necesita una fotografía más clara para poder evaluar la planta.",
    "recommendation": [
        "Toma una fotografía más cercana, enfocada y bien iluminada de la zona afectada.",
        "Evita el uso de zoom digital excesivo; acércate físicamente en su lugar.",
        "Incluye en la foto hojas, tallos o brotes junto con la zona de interés para dar más contexto."
    ],
    "prevention": [
        "Fotografía con luz natural y sin contraluz, evitando sombras fuertes sobre la zona de interés.",
        "Mantén la cámara estable para evitar imágenes borrosas.",
        "Acerca la cámara a hojas, tallos o brotes en vez de recortar o hacer zoom digital."
    ]
}

------------------------------------------------------------

EJEMPLO 6 - LA IMAGEN NO MUESTRA UNA PLANTA

{
    "status": "inconcluso",
    "nombre_planta": "No identificada",
    "nombre_cientifico": "No disponible",
    "familia": "No disponible",
    "caracteristicas": {
        "hoja": "Información no disponible",
        "tallo": "Información no disponible",
        "epoca": "Información no disponible",
        "clima": "Información no disponible",
        "riego": "Información no disponible"
    },
    "tipo_problema": "No se observa una planta",
    "observation": "La imagen proporcionada no muestra una planta o una parte de una planta que pueda analizarse.",
    "descripcion_general": "No aplica, ya que la imagen no muestra una planta.",
    "recommendation": [
        "Sube una fotografía clara de la planta, preferiblemente mostrando hojas, tallos, brotes, flores o la zona afectada."
    ],
    "prevention": [
        "No aplica."
    ]
}

============================================================

RECUERDA:

MARCHITEZ NO SIGNIFICA AUTOMÁTICAMENTE PLAGA.

HOJAS AMARILLAS NO SIGNIFICAN AUTOMÁTICAMENTE PLAGA.

MANCHAS NO SIGNIFICAN AUTOMÁTICAMENTE PLAGA.

UNA FLOR SECA NO SIGNIFICA AUTOMÁTICAMENTE PLAGA.

NO INVENTES INSECTOS.

NO INVENTES ENFERMEDADES.

PRIMERO OBSERVA Y DESPUÉS CLASIFICA.

RESPONDE ÚNICAMENTE EL JSON.
"""



    return {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": prompt
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": (
                        f"data:{mime_type};base64,"
                        f"{image_base64}"
                    )
                }
            }
        ]
    }


# ============================================================
# 6. FUNCIÓN PARA LIMPIAR JSON
# ============================================================

def limpiar_json(texto: str):

    texto = texto.strip()

    # Quitar ```json
    texto = re.sub(
        r"^```json\s*",
        "",
        texto,
        flags=re.IGNORECASE
    )

    # Quitar ```
    texto = re.sub(
        r"^```\s*",
        "",
        texto
    )

    texto = re.sub(
        r"\s*```$",
        "",
        texto
    )

    # Intento normal
    try:

        return json.loads(texto)

    except json.JSONDecodeError:

        pass

    # Intentar recuperar solo {...}
    inicio = texto.find("{")
    fin = texto.rfind("}")

    if inicio != -1 and fin != -1:

        posible_json = texto[
            inicio:fin + 1
        ]

        return json.loads(
            posible_json
        )

    raise ValueError(
        "No se encontró un JSON válido."
    )


# ============================================================
# 6.1 CARACTERÍSTICAS / RESPUESTA DE ERROR POR DEFECTO
# ============================================================

CARACTERISTICAS_NO_DISPONIBLES = {
    "hoja": "Información no disponible",
    "tallo": "Información no disponible",
    "epoca": "Información no disponible",
    "clima": "Información no disponible",
    "riego": "Información no disponible"
}


def prevencion_por_defecto(caracteristicas: dict) -> list:
    """
    Se usa únicamente si la IA respondió sin incluir "prevention"
    (o la envió vacía). Da consejos genéricos pero útiles en vez
    de "No disponible", apoyándose en el riego de la especie
    cuando se conoce.
    """

    riego = caracteristicas.get(
        "riego",
        "Información no disponible"
    )

    consejos = []

    if riego and riego != "Información no disponible":

        consejos.append(
            "Mantén el riego adecuado para esta especie "
            f"({riego})."
        )

    else:

        consejos.append(
            "Mantén un riego adecuado según el tipo de planta."
        )

    consejos.append(
        "Revisa la planta periódicamente (hojas, tallos y "
        "envés de las hojas) para detectar cambios a tiempo."
    )

    consejos.append(
        "Asegura buena ventilación e iluminación adecuada "
        "para la especie."
    )

    return consejos


def asegurar_lista(
    valor,
    valores_por_defecto: list
) -> list:
    """
    Normaliza "recommendation"/"prevention" a list[str], sin
    importar si la IA respondió con un array (lo esperado), un
    string suelto (fallback: se separa en oraciones), o si
    vino vacío/ausente (se usa el valor por defecto).
    """

    if isinstance(valor, list):

        limpio = [
            str(item).strip()
            for item in valor
            if str(item).strip()
        ]

        if limpio:
            return limpio

    elif isinstance(valor, str) and valor.strip():

        texto = valor.strip()

        partes = [
            parte.strip()
            for parte in re.split(r"(?<=[.!?])\s+", texto)
            if parte.strip()
        ]

        if partes:
            return partes

    return valores_por_defecto


def respuesta_error(
    tipo_problema: str,
    observation: str,
    recommendation: str
) -> dict:

    return {

        "status": "inconcluso",

        "nombre_planta": "No identificada",

        "nombre_cientifico": "No disponible",

        "familia": "No disponible",

        "caracteristicas": dict(
            CARACTERISTICAS_NO_DISPONIBLES
        ),

        "tipo_problema": tipo_problema,

        "severidad": "desconocida",

        "observation": observation,

        "descripcion_general": "No disponible.",

        "recommendation": [recommendation],

        "prevention": ["No disponible."]

    }


# ============================================================
# 7. ENDPOINT ANALIZAR
# ============================================================

@app.post("/analyze")
async def analizar(
    imagen: UploadFile = File(...)
):

    try:

        # ----------------------------------------------------
        # LEER ARCHIVO
        # ----------------------------------------------------

        contenido = await imagen.read()

        if not contenido:

            return respuesta_error(
                "error",
                "La imagen enviada está vacía.",
                "Selecciona otra fotografía."
            )


        # ----------------------------------------------------
        # TIPO DE IMAGEN
        # ----------------------------------------------------

        mime_type = (
            imagen.content_type
            or "image/jpeg"
        )


        formatos_permitidos = [

            "image/jpeg",

            "image/jpg",

            "image/png",

            "image/webp"

        ]


        if mime_type not in formatos_permitidos:

            return respuesta_error(
                "formato_no_compatible",
                "El formato de imagen no es compatible.",
                "Utiliza una fotografía JPG, PNG o WEBP."
            )


        # ----------------------------------------------------
        # BASE64
        # ----------------------------------------------------

        imagen_b64 = base64.b64encode(
            contenido
        ).decode("utf-8")


        # ----------------------------------------------------
        # CREAR MENSAJE
        # ----------------------------------------------------

        mensaje = create_analysis_prompt(

            imagen_b64,

            mime_type

        )


        # ----------------------------------------------------
        # HEADERS
        # ----------------------------------------------------

        headers = {

            "Authorization":
                f"Bearer {API_KEY}",

            "Content-Type":
                "application/json"

        }


        # ----------------------------------------------------
        # PAYLOAD
        # ----------------------------------------------------

        payload = {

            "model": MODEL,

            "messages": [
                mensaje
            ],

            "max_tokens": 1400,

            "temperature": 0.1,

            "stream": False

        }


        print(
            f"📤 Analizando: {imagen.filename}"
        )


        # ----------------------------------------------------
        # NVIDIA
        # ----------------------------------------------------

        response = requests.post(

            NVIDIA_URL,

            headers=headers,

            json=payload,

            timeout=120

        )


        # ----------------------------------------------------
        # ERROR NVIDIA
        # ----------------------------------------------------

        if response.status_code != 200:

            print(
                f"❌ NVIDIA: {response.status_code}"
            )

            print(
                response.text
            )

            return respuesta_error(
                "error_api",
                "No se pudo completar el análisis con la inteligencia artificial.",
                "Intenta nuevamente dentro de unos minutos."
            )


        # ----------------------------------------------------
        # RESPUESTA NVIDIA
        # ----------------------------------------------------

        datos = response.json()


        try:

            texto_respuesta = (
                datos["choices"][0]
                ["message"]["content"]
            )

        except (
            KeyError,
            IndexError,
            TypeError
        ):

            print(
                "❌ Formato inesperado:"
            )

            print(datos)

            return respuesta_error(
                "error_respuesta",
                "La inteligencia artificial devolvió una respuesta inesperada.",
                "Intenta nuevamente."
            )


        print(
            "✅ Respuesta recibida:"
        )

        print(
            texto_respuesta
        )


        # ----------------------------------------------------
        # CONVERTIR JSON
        # ----------------------------------------------------

        try:

            resultado = limpiar_json(
                texto_respuesta
            )

        except Exception as error:

            print(
                f"⚠️ Error interpretando JSON: {error}"
            )

            return respuesta_error(
                "desconocido",
                "La imagen fue analizada, pero no se pudo interpretar correctamente la respuesta.",
                "Intenta nuevamente con una fotografía más clara."
            )


        # ----------------------------------------------------
        # VALIDAR CAMPOS
        # ----------------------------------------------------

        estados_validos = [
            "sin_problemas",
            "plagas_presentes",
            "enfermedad_posible",
            "inconcluso"
        ]


        severidades_validas = [
            "leve",
            "moderada",
            "severa",
            "desconocida"
        ]


        # STATUS
        status = resultado.get(
            "status",
            "inconcluso"
        )

        if status not in estados_validos:

            status = "inconcluso"


        # SEVERIDAD
        severidad = resultado.get(
            "severidad",
            "desconocida"
        )

        if severidad not in severidades_validas:

            severidad = "desconocida"


        # CARACTERÍSTICAS DE LA PLANTA
        caracteristicas_ia = resultado.get(
            "caracteristicas",
            {}
        )

        if not isinstance(caracteristicas_ia, dict):

            caracteristicas_ia = {}

        caracteristicas = {

            campo: caracteristicas_ia.get(
                campo,
                valor_defecto
            )

            for campo, valor_defecto
            in CARACTERISTICAS_NO_DISPONIBLES.items()

        }


        # ----------------------------------------------------
        # RESPUESTA FINAL
        # ----------------------------------------------------

        respuesta_final = {

            "status":
                status,

            "nombre_planta":
                resultado.get(
                    "nombre_planta",
                    "No identificada"
                ),

            "nombre_cientifico":
                resultado.get(
                    "nombre_cientifico",
                    "No disponible"
                ),

            "familia":
                resultado.get(
                    "familia",
                    "No disponible"
                ),

            "caracteristicas":
                caracteristicas,

            "tipo_problema":
                resultado.get(
                    "tipo_problema",
                    "desconocido"
                ),

            "severidad":
                severidad,

            "observation":
                resultado.get(
                    "observation",
                    "No existe suficiente información."
                ),

            "descripcion_general":
                resultado.get(
                    "descripcion_general"
                ) or "No disponible.",

            "recommendation":
                asegurar_lista(
                    resultado.get("recommendation"),
                    ["Realiza una revisión visual más cercana."]
                ),

            "prevention":
                asegurar_lista(
                    resultado.get("prevention"),
                    prevencion_por_defecto(caracteristicas)
                )

        }


        # ----------------------------------------------------
        # GUARDAR EN "MIS PLANTAS"
        # ----------------------------------------------------

        try:

            guardado = storage.guardar_analisis(
                respuesta_final,
                contenido,
                mime_type
            )

            respuesta_final["id"] = guardado["id"]
            respuesta_final["imagen_url"] = guardado["imagen_url"]
            respuesta_final["fecha"] = guardado["fecha"]

        except Exception as error_guardado:

            print(
                f"⚠️ No se pudo guardar en Mis Plantas: {error_guardado}"
            )


        print(
            "✅ Resultado final:"
        )

        print(
            json.dumps(
                respuesta_final,
                indent=4,
                ensure_ascii=False
            )
        )


        return respuesta_final


    # ========================================================
    # TIMEOUT
    # ========================================================

    except requests.exceptions.Timeout:

        print(
            "❌ Timeout NVIDIA"
        )

        return respuesta_error(
            "error_timeout",
            "El análisis tardó demasiado tiempo.",
            "Intenta nuevamente."
        )


    # ========================================================
    # ERROR CONEXIÓN
    # ========================================================

    except requests.exceptions.ConnectionError:

        print(
            "❌ Error de conexión con NVIDIA"
        )

        return respuesta_error(
            "error_conexion",
            "No se pudo conectar con el servicio de inteligencia artificial.",
            "Verifica la conexión a Internet e intenta nuevamente."
        )


    # ========================================================
    # ERROR GENERAL
    # ========================================================

    except Exception as e:

        print(
            f"❌ ERROR GENERAL: {str(e)}"
        )

        return respuesta_error(
            "error",
            f"Ocurrió un error durante el análisis: {str(e)}",
            "Intenta nuevamente."
        )


# ============================================================
# 7.1 ENDPOINTS "MIS PLANTAS"
# ============================================================

@app.get("/plantas")
def listar_plantas():

    return storage.listar_analisis()


@app.get("/plantas/{id_planta}")
def obtener_planta(id_planta: int):

    planta = storage.obtener_analisis(id_planta)

    if planta is None:

        raise HTTPException(
            status_code=404,
            detail="Planta no encontrada."
        )

    return planta


@app.delete("/plantas/{id_planta}")
def eliminar_planta(id_planta: int):

    eliminado = storage.eliminar_analisis(id_planta)

    if not eliminado:

        raise HTTPException(
            status_code=404,
            detail="Planta no encontrada."
        )

    return {
        "eliminado": True,
        "id": id_planta
    }


@app.delete("/plantas")
def eliminar_todas_las_plantas():

    cantidad = storage.eliminar_todos()

    return {
        "eliminado": True,
        "cantidad": cantidad
    }


# ============================================================
# 8. EJECUTAR SERVIDOR
# ============================================================

if __name__ == "__main__":

    import uvicorn


    print(
        "=" * 65
    )

    print(
        "🌿 DETECTOR DE PLAGAS EN PLANTAS ORNAMENTALES Y MEDICINALES"
    )

    print(
        "=" * 65
    )

    print(
        "API Key NVIDIA: ✅ configurada"
    )

    print(
        f"Modelo: {MODEL}"
    )

    print(
        "Servidor: http://localhost:8000"
    )

    print(
        "Documentación: http://localhost:8000/docs"
    )

    print(
        "=" * 65
    )


    uvicorn.run(

        app,

        host="0.0.0.0",

        port=8000,

        log_level="info"

    )