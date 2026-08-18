import os
import base64
import json
import re
import requests

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv


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
    title="Detector de Plagas en Plantas Ornamentales",
    version="1.0"
)


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
# 4. RUTAS DE PRUEBA
# ============================================================

@app.get("/")
def raiz():

    return {
        "mensaje": "Backend funcionando ✅"
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
ERES UN ESPECIALISTA EN ENTOMOLOGÍA, FITOPATOLOGÍA
Y CUIDADO DE PLANTAS ORNAMENTALES.

Tu tarea es analizar visualmente la fotografía proporcionada
e identificar si la planta presenta una plaga, enfermedad,
marchitez u otro problema visible.

El objetivo principal del sistema es detectar PLAGAS,
pero también debes reconocer otros problemas visibles de la planta.

IMPORTANTE:

- Analiza únicamente lo que realmente puede observarse en la imagen.
- NO inventes plagas, enfermedades ni síntomas.
- NO afirmes una causa si la imagen no proporciona evidencia suficiente.
- Si existe incertidumbre, utiliza el estado "inconcluso".

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

representa el PROBLEMA PRINCIPAL que será mostrado al usuario.

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
9. DESCRIPCIÓN DEL PROBLEMA
============================================================

La propiedad:

"observation"

será mostrada en la interfaz como:

"Descripción del problema"

Por lo tanto, debe explicar claramente QUÉ SE OBSERVA
EN LA IMAGEN.

Describe únicamente características visibles.

Sé específico pero breve.

Usa aproximadamente 1 a 3 oraciones.

Ejemplo correcto:

"Se observan numerosos insectos pequeños verdes agrupados
alrededor de los brotes jóvenes y del botón floral,
compatibles visualmente con pulgones."

Ejemplo correcto:

"La flor presenta pétalos caídos, arrugados y con pérdida
de firmeza. No se observan insectos visibles ni señales
claras de infestación."

Ejemplo incorrecto:

"La planta tiene pulgones porque está amarilla."

NO inventes características que no puedan observarse.

============================================================
10. SOLUCIÓN
============================================================

La propiedad:

"recommendation"

será mostrada en la interfaz como:

"Solución"

Debe indicar qué puede hacer el usuario frente al problema
identificado.

La solución debe ser:

- Clara.
- Práctica.
- Breve.
- Segura.
- Apropiada para una planta ornamental doméstica.

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

- Retirar partes muy afectadas.
- Mejorar ventilación.
- Evitar mantener hojas constantemente húmedas.
- Revisar las condiciones de cultivo.
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
11. FORMATO DE RESPUESTA
============================================================

RESPONDE ÚNICAMENTE CON JSON VÁLIDO.

NO utilices Markdown.

NO escribas ```json.

NO escribas ```.

NO agregues explicaciones antes del JSON.

NO agregues explicaciones después del JSON.

UTILIZA EXACTAMENTE ESTAS CUATRO PROPIEDADES:

{
    "status": "sin_problemas|plagas_presentes|enfermedad_posible|inconcluso",
    "tipo_problema": "nombre breve del problema",
    "observation": "descripción del problema observado",
    "recommendation": "solución práctica recomendada"
}

NO agregues la propiedad "severidad".

NO agregues ninguna propiedad adicional.

============================================================
12. EJEMPLOS
============================================================

EJEMPLO 1 - PULGONES

{
    "status": "plagas_presentes",
    "tipo_problema": "Pulgones",
    "observation": "Se observan numerosos insectos pequeños verdes agrupados alrededor de los brotes jóvenes y del botón floral, compatibles visualmente con pulgones.",
    "recommendation": "Aislar temporalmente la planta, revisar brotes y envés de las hojas y retirar los insectos con agua. Si persisten, utilizar jabón potásico siguiendo las instrucciones del producto."
}

------------------------------------------------------------

EJEMPLO 2 - FLOR MARCHITA

{
    "status": "enfermedad_posible",
    "tipo_problema": "Marchitez o estrés hídrico",
    "observation": "La flor presenta pétalos caídos, arrugados y con pérdida visible de firmeza. No se observan insectos ni signos claros de infestación.",
    "recommendation": "Revisar la humedad del sustrato, la frecuencia de riego y el drenaje. Evitar tanto el exceso como la falta de agua y retirar las flores completamente secas."
}

------------------------------------------------------------

EJEMPLO 3 - PLANTA SALUDABLE

{
    "status": "sin_problemas",
    "tipo_problema": "Ninguno",
    "observation": "La planta presenta una apariencia general saludable y no se observan insectos, daños, marchitez significativa ni signos evidentes de enfermedad.",
    "recommendation": "Continuar con el cuidado habitual y revisar periódicamente hojas, tallos, brotes y flores."
}

------------------------------------------------------------

EJEMPLO 4 - IMAGEN NO CONCLUYENTE

{
    "status": "inconcluso",
    "tipo_problema": "Imagen no concluyente",
    "observation": "La fotografía no muestra suficiente detalle para identificar con confianza la presencia de una plaga, enfermedad u otro problema.",
    "recommendation": "Tomar una fotografía más cercana, enfocada y bien iluminada de la zona afectada."
}

------------------------------------------------------------

EJEMPLO 5 - LA IMAGEN NO MUESTRA UNA PLANTA

{
    "status": "inconcluso",
    "tipo_problema": "No se observa una planta",
    "observation": "La imagen proporcionada no muestra una planta o una parte de una planta que pueda analizarse.",
    "recommendation": "Subir una fotografía clara de la planta, preferiblemente mostrando hojas, tallos, brotes, flores o la zona afectada."
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

            return {

                "status": "inconcluso",

                "tipo_problema": "error",

                "severidad": "desconocida",

                "observation":
                    "La imagen enviada está vacía.",

                "recommendation":
                    "Selecciona otra fotografía."

            }


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

            return {

                "status": "inconcluso",

                "tipo_problema": "formato_no_compatible",

                "severidad": "desconocida",

                "observation":
                    "El formato de imagen no es compatible.",

                "recommendation":
                    "Utiliza una fotografía JPG, PNG o WEBP."

            }


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

            "max_tokens": 800,

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

            return {

                "status": "inconcluso",

                "tipo_problema": "error_api",

                "severidad": "desconocida",

                "observation":
                    "No se pudo completar el análisis con la inteligencia artificial.",

                "recommendation":
                    "Intenta nuevamente dentro de unos minutos."

            }


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

            return {

                "status": "inconcluso",

                "tipo_problema": "error_respuesta",

                "severidad": "desconocida",

                "observation":
                    "La inteligencia artificial devolvió una respuesta inesperada.",

                "recommendation":
                    "Intenta nuevamente."

            }


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

            return {

                "status": "inconcluso",

                "tipo_problema": "desconocido",

                "severidad": "desconocida",

                "observation":
                    "La imagen fue analizada, pero no se pudo interpretar correctamente la respuesta.",

                "recommendation":
                    "Intenta nuevamente con una fotografía más clara."

            }


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


        # ----------------------------------------------------
        # RESPUESTA FINAL
        # ----------------------------------------------------

        respuesta_final = {

            "status":
                status,

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

            "recommendation":
                resultado.get(
                    "recommendation",
                    "Realiza una revisión visual más cercana."
                )

        }


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

        return {

            "status": "inconcluso",

            "tipo_problema": "error_timeout",

            "severidad": "desconocida",

            "observation":
                "El análisis tardó demasiado tiempo.",

            "recommendation":
                "Intenta nuevamente."

        }


    # ========================================================
    # ERROR CONEXIÓN
    # ========================================================

    except requests.exceptions.ConnectionError:

        print(
            "❌ Error de conexión con NVIDIA"
        )

        return {

            "status": "inconcluso",

            "tipo_problema": "error_conexion",

            "severidad": "desconocida",

            "observation":
                "No se pudo conectar con el servicio de inteligencia artificial.",

            "recommendation":
                "Verifica la conexión a Internet e intenta nuevamente."

        }


    # ========================================================
    # ERROR GENERAL
    # ========================================================

    except Exception as e:

        print(
            f"❌ ERROR GENERAL: {str(e)}"
        )

        return {

            "status": "inconcluso",

            "tipo_problema": "error",

            "severidad": "desconocida",

            "observation":
                f"Ocurrió un error durante el análisis: {str(e)}",

            "recommendation":
                "Intenta nuevamente."

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
        "🌿 DETECTOR DE PLAGAS EN PLANTAS ORNAMENTALES"
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