# Emergexia

<<<<<<< HEAD
Sistema de Gestión Médica y de Emergencias. Login y panel con módulos
(Doctores, Ambulancias, Emergencias, Operadores y Configuración).

- **MongoDB** guarda los datos (base principal).
- **Apache Spark** procesa esos datos para análisis (resumen por estado) y se inicia solo cuando hace falta.

```
emergexia/
├── backend/            API en Python (FastAPI)
│   ├── diagnostico.py      ← revisa Python, Java, MongoDB, Spark y el backend
│   ├── crear_usuario.py    ← crea usuarios / cambia contraseñas en MongoDB
│   ├── probar_guardado.py  ← guarda y lee un dato de prueba en tu MongoDB
│   └── app/
│       ├── mongo.py        ← conexión a MongoDB
│       ├── dbschema.py     ← colecciones, validaciones e índices
│       ├── repository.py   ← lectura/escritura de datos y usuarios
│       ├── spark.py        ← conexión a Spark (SparkSession)
│       ├── analytics.py    ← análisis con Spark sobre los datos de Mongo
│       ├── readiness.py    ← arranque seguro (no tumba la API si algo falla)
│       ├── security.py     ← contraseñas (PBKDF2) y tokens JWT
│       ├── routers/        ← auth, módulos, estado de servicios
│       └── main.py
├── frontend/           React + Vite
│   └── src/
│       ├── pages/          ← Login, Home, ModulePage, SettingsPage
│       ├── components/     ← Layout, Logo, Heartbeat (animación Lottie)
│       ├── lib/            ← api.js, auth.jsx, modules.js (define los módulos)
│       ├── assets/         ← ambulance.jpg, heartbeat.json
│       └── styles/app.css  ← colores y estilos (variables al inicio)
└── docker-compose.yml  (opcional, no hace falta)
=======
Sistema de Gestión Médica y de Emergencias. Interfaz de inicio de sesión y panel con módulos
(Doctores, Ambulancias, Emergencias, Operadores y Configuración), con un backend que **se conecta a Apache Spark**.

```
emergexia/
├── backend/            API en Python (FastAPI) + PySpark
│   └── app/
│       ├── spark.py        ← conexión a Spark (SparkSession)
│       ├── tables.py       ← tablas Parquet leídas/escritas con Spark + datos de ejemplo
│       ├── readiness.py    ← arranque seguro de Spark (no tumba la API si falla)
│       ├── security.py     ← contraseñas (PBKDF2) y tokens JWT
│       ├── routers/        ← auth, módulos, estado de Spark
│       └── main.py
├── frontend/           React + Vite (login, panel, módulos, configuración)
│   └── src/
│       ├── pages/          ← Login, Home, ModulePage, SettingsPage
│       ├── components/     ← Layout (menú lateral + barra superior), Logo
│       ├── lib/            ← api.js, auth.jsx, modules.js (define los módulos)
│       └── styles/app.css  ← colores y estilos (variables al inicio)
└── docker-compose.yml  (opcional)
>>>>>>> ecb314e0be1671f363a199180d1176f6feb81edb
```

## Requisitos

<<<<<<< HEAD
- Python 3.10+ (probado con 3.12 y 3.13)
- Node.js 18+
- Un clúster de **MongoDB Atlas** (o un MongoDB local)
- Java 17 o 21 — **solo** para las funciones de Spark (`java -version`)
=======
- Python 3.10+
- **Java 11, 17 o 21** (lo necesita Spark) → comprueba con `java -version`
- Node.js 18+
>>>>>>> ecb314e0be1671f363a199180d1176f6feb81edb

## Puesta en marcha

### 1. Backend (terminal 1)

```bash
cd backend
python -m venv .venv
<<<<<<< HEAD
.venv\Scripts\activate             # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env             # Mac/Linux: cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

=======
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

La primera vez Spark tarda unos segundos en arrancar y crea las tablas con datos de ejemplo en `backend/data/`.
Documentación interactiva de la API: <http://localhost:8000/docs>

>>>>>>> ecb314e0be1671f363a199180d1176f6feb81edb
### 2. Frontend (terminal 2)

```bash
cd frontend
npm install
npm run dev
```

<<<<<<< HEAD
Abre <http://localhost:5173> · usuario `admin` · contraseña `admin123`
(cámbiala con `python crear_usuario.py admin`).

## Base de datos (MongoDB Atlas)

La conexión ya viene configurada en `backend/.env` (`MONGO_URI`, `MONGO_DB=emergexia`). Al arrancar, el backend:

1. se conecta a Atlas,
2. **crea las colecciones** (tablas) con validación de campos e índices si no existen,
3. crea el usuario administrador la primera vez (`ADMIN_*` en `.env`).

Colecciones:

| Colección | Qué guarda | Campos principales | Único |
|-----------|------------|--------------------|-------|
| `users` | Quién puede iniciar sesión | `username`, `password_hash`, `full_name`, `role`, `active` | `username` |
| `doctors` | Personal médico | `nombre`, `especialidad`, `telefono`, `estado` | `id` |
| `ambulances` | Flota | `placa`, `tipo`, `conductor`, `estado` | `placa` |
| `emergencies` | Emergencias | `folio` (EMG-0001…), `descripcion`, `prioridad`, `estado`, `ambulancia` | `folio` |
| `operators` | Operadores de la central | `nombre`, `turno`, `extension`, `estado` | `id` |
| `counters` | Contadores internos de `id` | — | — |

Todas llevan `id` autoincremental y `created_at`. Para ver las colecciones: abre MongoDB Compass y refresca.

**Antes de la primera ejecución, en Atlas:** *Network Access → Add IP Address → Add current IP address*
(sin esto Atlas rechaza la conexión). Si trabajas desde otra red, agrégala también.

**Usuarios y contraseñas** (la contraseña se guarda cifrada en `users`, no en `.env`):

```bash
python crear_usuario.py admin                                   # cambia la contraseña de admin
python crear_usuario.py maria --nombre "María Pérez" --rol Operador   # crea otro usuario
```

**Datos de ejemplo:** pon `SEED_DEMO_DATA=true` en `.env` para rellenar las colecciones vacías con doctores,
ambulancias, etc. (por defecto quedan vacías, listas para tus datos reales).

**Seguridad:** `backend/.env` contiene tu contraseña de Atlas y está en `.gitignore`. No lo subas a GitHub ni lo compartas.

## Spark

Se conecta bajo demanda (la primera consulta tarda unos segundos). Config en `backend/.env`:

| Variable | Para qué sirve |
|----------|----------------|
| `SPARK_MASTER` | `local[*]` (embebido, por defecto) · `spark://host:7077` (clúster) · `yarn` · `k8s://…` |
| `SPARK_APP_NAME` | Nombre de la aplicación (`Emergexia`) |
| `SPARK_UI_ENABLED` | `true` abre la UI de Spark en el puerto 4040 |
| `SPARK_DRIVER_HOST` | IP del backend si usas un clúster remoto |

Hoy Spark se usa en `GET /api/dashboard/summary`: lee los documentos de MongoDB y calcula los conteos por estado
con un DataFrame (`groupBy`). El estado real de la conexión está en **Configuración → Conexión con Spark**.
Si Spark no arranca, el resto del sistema sigue funcionando.

## Guardé algo en la web y no aparece

**La prueba clave:** mira la terminal del backend mientras pulsas *Guardar*. Debe aparecer
`POST /api/ambulancias 201` y `Guardado en MongoDB emergexia.ambulances (id=…)`.
Si **no aparece nada**, la página no está hablando con ese backend (hay otro en el puerto 8000, o el frontend y el
backend corren en "mundos" distintos: uno en Windows y otro en WSL).

**Solución limpia: usar un puerto nuevo** (así ningún backend viejo puede interferir):

```bash
# terminal 1 (backend)
uvicorn app.main:app --reload --port 8010

# terminal 2 (frontend, en la MISMA máquina/WSL que el backend)
VITE_API_TARGET=http://127.0.0.1:8010 npm run dev      # o copia frontend/.env.local.example a .env.local
```

Al arrancar, el frontend imprime en su terminal a qué backend apunta:
`✔ Backend http://127.0.0.1:8010 (v2.0-mongodb) conectado a MongoDB · base 'emergexia'`.
Si ves `⚠` o `✖`, el mensaje dice qué falta.

En WSL: `ss -ltnp | grep 8000` muestra qué proceso usa el puerto (`kill <PID>`); en Windows,
`netstat -ano | findstr :8000` y `taskkill /PID <PID> /F`.

Al guardar, la página muestra un aviso verde: **"✓ Ambulancia guardada en MongoDB (emergexia.ambulances), id N"**
y debajo de la tabla dice de dónde leyó los datos. Según lo que veas:

| Qué ves | Causa probable | Qué hacer |
|---------|----------------|-----------|
| Aviso amarillo *"versión ANTIGUA del backend"* | Un backend viejo sigue vivo en el puerto 8000 y atiende la página | `python diagnostico.py` te da el PID; ciérralo (`taskkill /PID <PID> /F`) y arranca uno solo |
| Aviso rojo con un error | La base rechazó el dato (duplicado, validación, conexión) | Lee el mensaje; `python probar_guardado.py` prueba la base sin la web |
| Aviso verde, pero Compass no lo muestra | Compass no se actualiza solo | Botón de refrescar en Compass; comprueba que miras la base `emergexia` |
| Nada de lo anterior | Página con datos viejos | `Ctrl + F5`, y botón **Actualizar** de la tabla |

Si arrancas `uvicorn` y ves `address already in use` / `[Errno 10048]`, hay otro backend usando el puerto: ciérralo primero.

## Si algo falla

Ejecuta primero el diagnóstico (en `backend`, con el entorno virtual activado):

```bash
python diagnostico.py          # o: python diagnostico.py --rapido  (sin probar Spark)
```

| Mensaje | Qué significa | Solución |
|---------|---------------|----------|
| Login: `El backend no respondió (código 500)` | El backend no está corriendo | En `backend`: `uvicorn app.main:app --reload --port 8000` y deja esa terminal abierta |
| `MongoDB no está disponible. No se pudo conectar a Atlas…` | Tu IP no está permitida en Atlas, o no hay internet/VPN | Atlas → Network Access → Add current IP address |
| `No se pudo resolver o interpretar MONGO_URI` | URI mal copiada o DNS que bloquea `mongodb+srv` | Revisa la URI; prueba otra red o usa la cadena "standard" de Atlas |
| `MongoDB rechazó las credenciales` | Usuario/contraseña de `MONGO_URI` | Atlas → Database Access; si la contraseña tiene símbolos, codifícalos (`@`→`%40`) |
| `Spark no está disponible…` | Java/Spark no arrancó | Solo afecta a Configuración→Spark y al resumen. Revisa `diagnostico.py` |
| `Usuario o contraseña incorrectos` | Credenciales incorrectas | Primera vez: `admin` / `admin123`. Si la olvidaste: `python crear_usuario.py admin` |

Si MongoDB no responde, el login y las pantallas muestran el motivo exacto en lugar de un error genérico.
=======
Abre <http://localhost:5173>

### Acceso inicial

| Usuario | Contraseña |
|---------|------------|
| `admin` | `admin123` |

Cámbialos en `backend/.env` (`ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_NAME`) y reinicia el backend.
Cambia también `JWT_SECRET`. El login **no depende de Spark**: puedes entrar aunque Spark falle.

## Conexión a Spark

Toda la configuración está en `backend/.env`:

| Variable | Para qué sirve |
|----------|----------------|
| `SPARK_MASTER` | `local[*]` (Spark embebido, por defecto) · `spark://host:7077` (clúster standalone) · `yarn` · `k8s://…` |
| `SPARK_APP_NAME` | Nombre de la aplicación en Spark (`Emergexia`) |
| `SPARK_UI_ENABLED` | `true` abre la UI de Spark en el puerto 4040 |
| `SPARK_DRIVER_HOST` | IP del backend si usas un clúster remoto |
| `DATA_DIR` | Dónde se guardan las tablas (Parquet). Acepta `hdfs://`, `s3a://`, etc. |

Cómo se usa Spark hoy:

- Cada tabla (`doctors`, `ambulances`, `emergencies`, `operators`) es una carpeta Parquet.
- Las listas y los conteos del resumen (`GET /api/dashboard/summary`) se calculan con DataFrames de Spark.
- En **Configuración** de la app hay un botón *Verificar* que muestra el estado real de la conexión
  (`GET /api/spark/status`: master, versión, ID de aplicación).

> Nota: cada alta añade un archivo Parquet pequeño. Es ideal para arrancar y para clústeres;
> más adelante podemos pasar a Delta Lake o a una base de datos con Spark por encima.

## Si el login no te deja entrar

Primero ejecuta el diagnóstico (en la carpeta `backend`, con el entorno virtual activado):

```bash
python diagnostico.py
```

Revisa Python, paquetes, Java, si el backend está corriendo y si Spark puede leer y escribir. Cada problema trae la solución.

| Mensaje en el login | Qué significa | Solución |
|---------------------|---------------|----------|
| `El backend no respondió (código 500)` | El backend no está corriendo o se cerró al arrancar | Arráncalo: `uvicorn app.main:app --reload --port 8000` y no cierres esa terminal |
| `Usuario o contraseña incorrectos` | Credenciales distintas a `.env` | Por defecto `admin` / `admin123` |

Si Spark falla (Java ausente, Windows sin `winutils`…), el login sigue funcionando y las pantallas de datos
muestran el motivo; también lo ves en <http://localhost:8000/api/health> (`spark_error`).

## Con Docker (opcional)

```bash
docker compose up --build
```

Web en <http://localhost:8080> y API en <http://localhost:8000/docs>.
>>>>>>> ecb314e0be1671f363a199180d1176f6feb81edb

## API principal

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/auth/login` | Devuelve token JWT y datos del usuario |
| GET | `/api/auth/me` | Usuario de la sesión |
<<<<<<< HEAD
| GET / POST | `/api/doctores` · `/api/ambulancias` · `/api/emergencias` · `/api/operadores` | Listar / crear (MongoDB). Duplicados → 409 |
| GET | `/api/dashboard/summary` | Conteos por estado (Spark sobre datos de Mongo) |
| GET | `/api/mongo/status` · `/api/spark/status` | Estado de cada conexión |
| GET | `/api/health` | Estado de la API (sin login) |

Documentación interactiva: <http://localhost:8000/docs>

## Personalizar

- **Colores**: variables `--red-*` al inicio de `frontend/src/styles/app.css`.
- **Módulos, columnas y formularios**: `frontend/src/lib/modules.js`.
- **Campos nuevos**: `backend/app/schemas.py` (validación). Mongo no exige esquema: basta con añadir el campo.
- **Foto y animación del login**: `frontend/src/assets/ambulance.jpg` y `heartbeat.json`.
=======
| GET / POST | `/api/doctores` · `/api/ambulancias` · `/api/emergencias` · `/api/operadores` | Listar / crear |
| GET | `/api/dashboard/summary` | Conteos por estado (Spark) |
| GET | `/api/spark/status` | Estado de la conexión a Spark |
| GET | `/api/health` | Estado de la API y de Spark (sin login) |

## Personalizar

- **Foto y animación del login**: `frontend/src/assets/ambulance.jpg` y `frontend/src/assets/heartbeat.json` (Lottie). Reemplaza los archivos con el mismo nombre para cambiarlos. La animación se pinta de blanco por código en `components/Heartbeat.jsx`; usa `<Heartbeat recolor={false} />` para ver sus colores originales.
- **Colores**: variables `--red-*` al inicio de `frontend/src/styles/app.css`.
- **Módulos, columnas y formularios**: `frontend/src/lib/modules.js`.
- **Campos/tablas nuevas**: `backend/app/tables.py` (esquemas) y `backend/app/schemas.py` (validación).
>>>>>>> ecb314e0be1671f363a199180d1176f6feb81edb

## Machine Learning: triage de ambulancias

Aplica al proyecto las Prácticas 04 (entrenamiento / validación / prueba) y 05 (comparación de
Decision Tree, Random Forest y KNN). El modelo responde: **¿la emergencia requiere ambulancia
Avanzada?** a partir de edad, frecuencia cardiaca, SpO2, presión sistólica, Glasgow y dolor torácico.
Complementa la regla lógica `M = u ∧ (p → v)` de `app/logica.py`.

```
backend/
├── entrenar_ml.py        ← entrena, compara, corre los experimentos A/B/C y genera gráficas
├── ml_resultados/        ← tablas CSV, gráficas PNG, reporte.json y el modelo (.joblib)
└── app/
    ├── ml/datos.py           ← datos sintéticos (1000 emergencias ficticias)
    ├── ml/entrenamiento.py   ← división 60/20/20, modelos, métricas, selección por F2
    ├── ml/prediccion.py      ← carga el modelo y predice (lo usa la API)
    └── routers/ml.py         ← POST /api/ml/predecir · GET /api/ml/reporte
frontend/src/components/PanelTriageML.jsx  ← panel en "Nueva emergencia"
```

```bash
cd backend
pip install -r requirements.txt
python entrenar_ml.py
```

Se selecciona el modelo con **F2-score** (pesa más el recall): dejar sin ambulancia Avanzada a un
paciente grave (falso negativo) es peor que enviar una Avanzada de más. Si no se ha corrido
`entrenar_ml.py`, la API entrena el modelo la primera vez que se usa.

> Datos sintéticos con fines educativos: no es un protocolo clínico y la decisión final es del personal médico.
